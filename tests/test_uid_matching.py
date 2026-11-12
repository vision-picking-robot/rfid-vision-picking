"""Partial / noisy UIDs from the Bluetooth reader are matched to exactly one DB tag."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from robot_rfid.api_server import install_rfid_routes
from robot_rfid.database import SEEDS, Database, clean_uid, match_uid

KNOWN = [seed[0] for seed in SEEDS]


def test_seed_uids_follow_reader_values():
    assert KNOWN == ['0B71E55D', '0B71E75D', '0B71E65D', '0B71ED5D']


@pytest.mark.parametrize('raw, expected', [
    ('0B71E55D', '0B71E55D'),
    ('0b 71 e5 5d', '0B71E55D'),
    ('0B:71:E7:5D', '0B71E75D'),
    ('E75D', '0B71E75D'),        # 4 of 8 chars
    ('71E6', '0B71E65D'),
    ('E55D', '0B71E55D'),
    ('0B71EDFF', '0B71ED5D'),    # last byte garbled, distinguishing byte intact
])
def test_partial_reads_resolve_to_one_tag(raw, expected):
    assert match_uid(raw, KNOWN) == expected


@pytest.mark.parametrize('raw', ['0B71', '0B71E', '0B71FF5D'])
def test_fragments_shared_by_several_tags_are_rejected(raw):
    with pytest.raises(ValueError, match='ambiguous'):
        match_uid(raw, KNOWN)


@pytest.mark.parametrize('raw', ['E7', '12345678', ''])
def test_short_or_unrelated_reads_are_unknown(raw):
    with pytest.raises(KeyError):
        match_uid(raw, KNOWN)


def test_clean_uid():
    assert clean_uid(' 0b-71:e5 5d ') == '0B71E55D'


def test_existing_db_moves_product_to_seed_uid_with_history(tmp_path):
    path = tmp_path / 'rfid.db'
    Database(path).initialize()
    with sqlite3.connect(path) as db:  # simulate a DB created with an older seed UID and one finished task
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute("UPDATE product_tag_mappings SET tag_uid='0BE5715D' WHERE sku_code='LOTTE-PEPERO-01'")
        db.execute("INSERT INTO tasks(task_id,event_id,tag_uid,quantity,completed,status,created_at) "
                   "VALUES ('t1','e1','0BE5715D',1,1,'COMPLETED','2026-11-10')")
    Database(path).initialize()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT tag_uid FROM product_tag_mappings WHERE sku_code='LOTTE-PEPERO-01'").fetchone()[0] == '0B71E55D'
        assert db.execute("SELECT tag_uid FROM tasks WHERE task_id='t1'").fetchone()[0] == '0B71E55D'
        assert db.execute('SELECT COUNT(*) FROM product_tag_mappings').fetchone()[0] == 4
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_api_queues_partial_uid_and_rejects_ambiguous(tmp_path):
    app = FastAPI()
    install_rfid_routes(app, tmp_path / 'rfid.db')
    with TestClient(app) as client:
        assert client.get('/api/v1/tags/E75D').json()['tag_uid'] == '0B71E75D'
        body = client.post('/api/v1/scan-event', json={'uid': 'E75D'}).json()
        assert body['uid'] == '0B71E75D' and body['raw_uid'] == 'E75D' and body['created'] is True
        assert body['task']['tag_uid'] == '0B71E75D'
        ambiguous = client.post('/api/v1/scan-event', json={'uid': '0B71'})
        assert ambiguous.status_code == 409 and 'ambiguous' in ambiguous.json()['detail']
        assert client.post('/api/v1/scan-event', json={'uid': 'E7'}).status_code == 422


def test_retired_plush_toy_tag_is_dropped_from_an_existing_db(tmp_path):
    path = tmp_path / 'rfid.db'
    Database(path).initialize()
    with sqlite3.connect(path) as db:  # a DB created while the toy tag was still seeded, with finished history
        db.execute("INSERT INTO product_tag_mappings (tag_uid,sku_code,product_name,category,target_class_id,"
                   "yolo_class_name,inbound_at,expired_at,retail_price,target_box_id) VALUES "
                   "('0B71EC5D','TOY-PLUSH-MINI','곰인형','TOY',4,'plush_toy','2026-09-01','9999-12-31',8900,'BOX-05')")
        db.execute("INSERT INTO tasks(task_id,event_id,tag_uid,quantity,status,created_at) "
                   "VALUES ('t1','e1','0B71EC5D',1,'DEFECTIVE','2026-11-12')")
    Database(path).initialize()
    database = Database(path)
    assert database.product('0B71EC5D') is None
    assert [p['tag_uid'] for p in database.products()] == KNOWN
    with pytest.raises((KeyError, ValueError)):  # no longer registered: rejected, never matched to a product
        database.resolve_uid('0B71EC5D')

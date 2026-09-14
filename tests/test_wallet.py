"""Wallet & coin tests (vision.txt §14: Wallet tests + V1 decisions)."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.main import app


def test_upload_reward_applied(client, user_factory, upload) -> None:
    auth = user_factory("w-reward")
    upload(auth["headers"], "W1")
    assert client.get("/coins/balance", headers=auth["headers"]).json()["balance"] == 10


def test_daily_reward_cap_enforced(client, user_factory, upload) -> None:
    """> 5 rewarded uploads/day; further uploads succeed but earn nothing."""
    auth = user_factory("w-cap")
    for i in range(7):  # 7 distinct files, only 5 rewarded
        r = upload(auth["headers"], f"CAP{i}")
        assert r.status_code == 201, r.text
    balance = client.get("/coins/balance", headers=auth["headers"]).json()["balance"]
    assert balance == 50  # 5 × UPLOAD_REWARD(10), capped

    types = [
        t["transaction_type"]
        for t in client.get("/coins/transactions", headers=auth["headers"]).json()
    ]
    assert types.count("UPLOAD_REWARD") == 5


def test_download_until_zero_then_rejected(client, user_factory, upload) -> None:
    """Balance 10, cost 5: two paid downloads succeed, third → 409."""
    owner = user_factory("w-own")
    spender = user_factory("w-spend")
    note_id = upload(owner["headers"], "WZ").json()["id"]

    # Fund the spender with one upload reward (10 coins).
    upload(spender["headers"], "WZ-SEED")
    assert client.get("/coins/balance", headers=spender["headers"]).json()["balance"] == 10

    assert client.get(f"/notes/{note_id}/download", headers=spender["headers"]).status_code == 200
    assert client.get("/coins/balance", headers=spender["headers"]).json()["balance"] == 5
    assert client.get(f"/notes/{note_id}/download", headers=spender["headers"]).status_code == 200
    assert client.get("/coins/balance", headers=spender["headers"]).json()["balance"] == 0
    assert client.get(f"/notes/{note_id}/download", headers=spender["headers"]).status_code == 409


def test_zero_balance_cannot_download(client, user_factory, upload) -> None:
    """A user who never uploaded (balance 0) must be rejected cleanly."""
    fresh = user_factory("w-zero")
    owner = user_factory("w-zero-own")
    note_id = upload(owner["headers"], "WZN").json()["id"]
    r = client.get(f"/notes/{note_id}/download", headers=fresh["headers"])
    assert r.status_code == 409


def test_self_download_never_charged(client, user_factory, upload) -> None:
    """V1 decision: owners always download their own notes for free."""
    auth = user_factory("w-self")
    for i in range(7):  # cap on rewards but uploads still land
        upload(auth["headers"], f"SELF{i}")
    note_id = client.get("/notes/my", headers=auth["headers"]).json()["notes"][0]["id"]
    before = client.get("/coins/balance", headers=auth["headers"]).json()["balance"]
    assert client.get(f"/notes/{note_id}/download", headers=auth["headers"]).status_code == 200
    after = client.get("/coins/balance", headers=auth["headers"]).json()["balance"]
    assert before == after


def test_ledger_reconciles_with_balance(client, user_factory, upload) -> None:
    """Every coin movement is in the ledger; amounts sum to the balance."""
    auth = user_factory("w-ledger")
    upload(auth["headers"], "LG1")
    # Earn nothing more (cap), then spend 5 twice on someone's note.
    other = user_factory("w-ledger-own")
    note_id = upload(other["headers"], "LG2").json()["id"]
    client.get(f"/notes/{note_id}/download", headers=auth["headers"])
    client.get(f"/notes/{note_id}/download", headers=auth["headers"])

    balance = client.get("/coins/balance", headers=auth["headers"]).json()["balance"]
    txs = client.get("/coins/transactions", headers=auth["headers"]).json()
    assert sum(t["amount"] for t in txs) == balance  # 10 - 5 - 5 = 0
    assert all(
        {"id", "amount", "transaction_type", "created_at"} <= set(t) for t in txs
    )


def test_transactions_require_auth(client) -> None:
    assert client.get("/coins/transactions").status_code == 401
    assert client.get("/coins/balance").status_code == 401


def test_concurrent_downloads_never_overdraft(client, user_factory, upload) -> None:
    """§14: 'Concurrent spending → balance never becomes negative.'

    Three parallel 5-coin downloads against a 10-coin wallet: exactly two
    must succeed; row locking serializes the third into a clean 409.
    """
    owner = user_factory("w-race-own")
    spender = user_factory("w-race")
    note_id = upload(owner["headers"], "RACE").json()["id"]

    # Fund the spender to exactly 10 coins (one reward), then race.
    upload(spender["headers"], "RACE-SEED")
    assert client.get("/coins/balance", headers=spender["headers"]).json()["balance"] == 10

    headers = spender["headers"]

    def _download(_: int) -> int:
        # One client per thread: shares no connection pool state.
        c = TestClient(app)
        return c.get(f"/notes/{note_id}/download", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        codes = list(pool.map(_download, range(3)))

    assert codes.count(200) == 2, codes
    assert codes.count(409) == 1, codes
    assert client.get("/coins/balance", headers=spender["headers"]).json()["balance"] == 0

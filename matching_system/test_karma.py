"""
Karma Points System — Test Suite

Run:
  python -m matching_system.test_karma            (unit tests only)
  python -m matching_system.test_karma --live      (integration against running server)
"""
import asyncio
import sys


def test_tier_computation():
    """Verify compute_tier() at every boundary."""
    from matching_system.karma_models import compute_tier, KarmaTier, get_next_tier_threshold, get_tier_level

    print("\n[UNIT TEST] Tier Computation")
    print("-" * 60)

    cases = [
        (0,    None,                0,    100),
        (50,   None,                0,    100),
        (99,   None,                0,    100),
        (100,  KarmaTier.BEGINNER,  1,    300),
        (299,  KarmaTier.BEGINNER,  1,    300),
        (300,  KarmaTier.PATHFINDER, 2,   500),
        (499,  KarmaTier.PATHFINDER, 2,   500),
        (500,  KarmaTier.EXPLORER,  3,    1000),
        (999,  KarmaTier.EXPLORER,  3,    1000),
        (1000, KarmaTier.CONQUEROR, 4,    None),
        (5000, KarmaTier.CONQUEROR, 4,    None),
    ]

    for score, expected_tier, expected_level, expected_next in cases:
        tier = compute_tier(score)
        level = get_tier_level(tier)
        nxt = get_next_tier_threshold(score)
        assert tier == expected_tier, f"score={score}: expected {expected_tier}, got {tier}"
        assert level == expected_level, f"score={score}: expected level {expected_level}, got {level}"
        assert nxt == expected_next, f"score={score}: expected next {expected_next}, got {nxt}"
        tier_name = tier.value if tier else "none"
        print(f"  score={score:>5}  -> tier={tier_name:<12} level={level} next={nxt}")

    print("  All tier computation tests passed!")


def test_model_validation():
    """Verify Pydantic schema validation rules."""
    from matching_system.karma_models import KarmaAwardRequest, KarmaActionType, InboxShieldUpdate
    from pydantic import ValidationError

    print("\n[UNIT TEST] Model Validation")
    print("-" * 60)

    req = KarmaAwardRequest(
        user_id="user_001",
        action_type=KarmaActionType.SIGNUP_EMAIL_VERIFY,
        point_delta=20,
    )
    assert req.point_delta == 20
    print("  Valid award request accepted")

    try:
        KarmaAwardRequest(
            user_id="user_001",
            action_type=KarmaActionType.NO_SHOW_PENALTY,
            point_delta=10,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("  Penalty with positive delta rejected")

    try:
        KarmaAwardRequest(
            user_id="user_001",
            action_type=KarmaActionType.EVENT_RSVP,
            point_delta=-5,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("  Reward with negative delta rejected")

    req_admin = KarmaAwardRequest(
        user_id="user_001",
        action_type=KarmaActionType.ADMIN_ADJUSTMENT,
        point_delta=-50,
    )
    assert req_admin.point_delta == -50
    print("  Admin adjustment with negative delta accepted")

    try:
        InboxShieldUpdate(threshold=-1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("  Negative inbox shield threshold rejected")

    shield = InboxShieldUpdate(threshold=200)
    assert shield.threshold == 200
    print("  Valid inbox shield threshold accepted")

    print("  All model validation tests passed!")


async def test_integration():
    """Full integration test against running FastAPI + PostgreSQL."""
    import httpx

    base_url = "http://localhost:8000/api/v1"
    headers = {}

    print("\n" + "=" * 60)
    print("Karma Points System -- Integration Tests")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:

        print("\n[1] Testing Onboarding Boost (0 -> 100)...")
        onboarding_actions = [
            ("SIGNUP_EMAIL_VERIFY", 20),
            ("SIGNUP_PROFILE_PHOTO", 30),
            ("SIGNUP_VIBE_QUESTIONS", 30),
            ("SIGNUP_CLAIM_ID", 20),
        ]
        test_user = "user_karma_test_001"
        running_total = 0

        for action, delta in onboarding_actions:
            resp = await client.post("/karma/award", json={
                "user_id": test_user,
                "action_type": action,
                "point_delta": delta,
            })
            running_total += delta
            data = resp.json()
            print(f"  {action}: +{delta}  ->  score={data.get('karma_score', '?')}")

        resp = await client.get(f"/users/{test_user}/karma?include_ledger=true&limit=10")
        profile = resp.json()
        assert profile["karma_score"] == 100, f"Expected 100, got {profile['karma_score']}"
        assert profile["tier"] == "beginner", f"Expected beginner, got {profile['tier']}"
        print(f"  Onboarding complete: score={profile['karma_score']} tier={profile['tier']}")

        print("\n[2] Testing Engagement Loop...")
        engagement_actions = [
            ("EVENT_RSVP", 10),
            ("GPS_CHECKIN", 25),
            ("EVENT_PHOTO_POST", 15),
            ("PEER_ENDORSEMENT", 20),
        ]
        for action, delta in engagement_actions:
            resp = await client.post("/karma/award", json={
                "user_id": test_user,
                "action_type": action,
                "point_delta": delta,
                "reference_id": "event_test_001",
            })
            data = resp.json()
            print(f"  {action}: +{delta}  ->  score={data.get('karma_score', '?')}")

        print("\n[3] Testing Penalty Deduction...")
        resp = await client.post("/karma/award", json={
            "user_id": test_user,
            "action_type": "NO_SHOW_PENALTY",
            "point_delta": -10,
            "reference_id": "event_test_001",
        })
        data = resp.json()
        print(f"  NO_SHOW_PENALTY: -10  ->  score={data.get('karma_score', '?')}")

        print("\n[4] Testing Inbox Shield & Messaging Rules...")

        test_user_2 = "user_karma_test_002"
        await client.post("/karma/award", json={
            "user_id": test_user_2,
            "action_type": "SIGNUP_EMAIL_VERIFY",
            "point_delta": 20,
        })

        resp = await client.get(f"/users/{test_user}/karma/can-message/{test_user_2}")
        result = resp.json()
        print(f"  High->Low messaging: allowed={result.get('allowed', '?')}")

        resp = await client.get(f"/users/{test_user_2}/karma/can-message/{test_user}")
        result = resp.json()
        print(f"  Low->High messaging: allowed={result.get('allowed', '?')}")

        resp = await client.patch(f"/users/{test_user}/inbox-shield", json={"threshold": 200})
        print(f"  Inbox shield set to 200 for {test_user}")

    print("\n" + "=" * 60)
    print("All Integration Tests Completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("\nRunning Unit Tests...")
    test_tier_computation()
    test_model_validation()

    if "--live" in sys.argv:
        print("\nRunning Integration Tests (--live)...")
        asyncio.run(test_integration())
    else:
        print("\nSkipping integration tests. Use --live to run against a server.")

    print("\nAll Tests Passed!\n")

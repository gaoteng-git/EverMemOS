#!/usr/bin/env python3
"""Debug UserProfile find_one with operator syntax"""

import asyncio


async def main():
    from infra_layer.adapters.out.persistence.document.memory.user_profile import (
        UserProfile,
    )

    # Test Beanie operator syntax
    try:
        print("Testing UserProfile.user_id property...")
        field_expr = UserProfile.user_id
        print(f"✅ UserProfile.user_id = {field_expr}")
        print(f"   Type: {type(field_expr)}")

        # Test equality operator
        print("\nTesting equality operator...")
        test_value = "test_user"
        condition = UserProfile.user_id == test_value
        print(f"✅ UserProfile.user_id == '{test_value}' = {condition}")
        print(f"   Type: {type(condition)}")

        # Test find_one with operator
        print("\nTesting find_one with operator syntax...")
        from core.di import get_bean_by_type
        from infra_layer.adapters.out.persistence.repository.user_profile_raw_repository import (
            UserProfileRawRepository,
        )

        repo = get_bean_by_type(UserProfileRawRepository)
        print(f"✅ Repository: {repo}")
        print(f"✅ Model: {repo.model}")
        print(f"✅ Model type: {type(repo.model)}")

        # Try find_one with operator syntax
        result = await repo.model.find_one(
            UserProfile.user_id == "test_user", UserProfile.group_id == "test_group"
        )
        print(f"✅ find_one result: {result}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

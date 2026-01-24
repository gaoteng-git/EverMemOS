#!/usr/bin/env python3
"""Debug EventLogRecord serialization issue"""

import asyncio
from datetime import datetime
import uuid


async def main():
    from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
        EventLogRecord,
    )

    # Test creating an EventLogRecord
    try:
        record = EventLogRecord(
            user_id="test_user",
            atomic_fact="Test fact",
            parent_type="memcell",
            parent_id="parent_123",
            timestamp=datetime.now(),
        )
        print("✅ EventLogRecord created successfully")

        # Test model_dump
        data = record.model_dump(mode="python")
        print(f"✅ model_dump works, fields: {len(data)}")

        # Test model_dump_json
        json_str = record.model_dump_json()
        print(f"✅ model_dump_json works, length: {len(json_str)}")

        # Test insert
        print("\nTrying to insert...")
        await record.insert()
        print(f"✅ Insert successful, ID: {record.id}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

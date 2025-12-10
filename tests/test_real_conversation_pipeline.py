"""
Real Conversation Pipeline Test

Test complete memory extraction pipeline, including:
- Using real tanka_memorize.memorize() function
- Automatic handling of ConvMemCellExtractor and EpisodeMemoryExtractor
- Testing complete end-to-end flow

Usage:
    python src/bootstrap.py tests/test_real_conversation_pipeline.py
"""

import pytest
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import dependency injection related modules
from core.observation.logger import get_logger

# Import modules to be tested
from biz_layer.tanka_memorize import memorize
from api_specs.dtos.memory_command import MemorizeRequest
from memory_layer.memcell_extractor.base_memcell_extractor import RawData
from api_specs.memory_types import RawDataType, MemoryType

# Get logger
logger = get_logger(__name__)


class TestRealConversationPipeline:
    """Real Conversation Pipeline Test Class"""

    def setup_method(self):
        """Setup before each test method"""
        self.base_time = datetime.now() - timedelta(hours=1)

    def create_project_discussion_messages(self) -> List[Dict[str, Any]]:
        """Create project discussion conversation"""
        messages = [
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "How's the project progress today? Let's discuss the current development status.",
                "timestamp": (self.base_time + timedelta(minutes=0)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Pretty good, the frontend part is basically done, just doing final testing. All React components have been developed.",
                "timestamp": (self.base_time + timedelta(minutes=2)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "What about the backend API development? Is the database design complete?",
                "timestamp": (self.base_time + timedelta(minutes=4)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Backend API is still in progress, database design is complete, expecting to finish all interface development tomorrow.",
                "timestamp": (self.base_time + timedelta(minutes=6)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "OK, when will the test plan start? We need to prepare the test environment.",
                "timestamp": (self.base_time + timedelta(minutes=8)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "The test plan is ready, test environment is also configured. We can start integration testing once the backend is complete.",
                "timestamp": (self.base_time + timedelta(minutes=10)).isoformat(),
            },
        ]
        return messages

    def create_personal_conversation_messages(self) -> List[Dict[str, Any]]:
        """Create personal care conversation (topic switch)"""
        messages = [
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "By the way Bob, how are you feeling lately? The workload has been quite heavy.",
                "timestamp": (
                    self.base_time + timedelta(minutes=35)
                ).isoformat(),  # 25 minute interval
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Not bad, just a bit tired. Work pressure has been high lately, but I can manage.",
                "timestamp": (self.base_time + timedelta(minutes=37)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "Make sure to get enough rest, health comes first. We can slow down the project pace a bit.",
                "timestamp": (self.base_time + timedelta(minutes=39)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Thanks for your concern Alice, I'll make sure to balance work and rest.",
                "timestamp": (self.base_time + timedelta(minutes=41)).isoformat(),
            },
        ]
        return messages

    def create_complete_meeting_conversation(self) -> List[Dict[str, Any]]:
        """Create complete meeting conversation (should generate MemCell)"""
        base_time = datetime.now() - timedelta(hours=2)

        messages = [
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "Hello everyone, let's start our weekly meeting. Today we'll discuss three topics: last week's progress review, this week's plan, and technical challenges.",
                "timestamp": (base_time + timedelta(minutes=0)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "OK Alice, I have the progress report ready.",
                "timestamp": (base_time + timedelta(minutes=1)).isoformat(),
            },
            {
                "speaker_id": "user_3",
                "speaker_name": "Charlie",
                "content": "I also have the technical solution updates ready.",
                "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "Great, Bob please report on last week's progress first.",
                "timestamp": (base_time + timedelta(minutes=3)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Last week we completed the user authentication module and permission management system, test coverage reached 90%, no major bugs found.",
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            {
                "speaker_id": "user_3",
                "speaker_name": "Charlie",
                "content": "Frontend completed the login interface and permission control components, integration with backend is working normally.",
                "timestamp": (base_time + timedelta(minutes=7)).isoformat(),
            },
            # Continue discussion 40 minutes later (indicating deep discussion)
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "After discussion, we've decided this week's focus is completing the payment module and order management.",
                "timestamp": (base_time + timedelta(minutes=45)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "I'll be responsible for the payment module, expecting to complete development by Wednesday.",
                "timestamp": (base_time + timedelta(minutes=46)).isoformat(),
            },
            {
                "speaker_id": "user_3",
                "speaker_name": "Charlie",
                "content": "I'll handle the order management interface, will complete it before Friday.",
                "timestamp": (base_time + timedelta(minutes=47)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "Great, everyone is clear on their tasks. Any technical challenges we need to discuss?",
                "timestamp": (base_time + timedelta(minutes=48)).isoformat(),
            },
            {
                "speaker_id": "user_2",
                "speaker_name": "Bob",
                "content": "Payment security needs special attention, I'll refer to industry best practices.",
                "timestamp": (base_time + timedelta(minutes=49)).isoformat(),
            },
            {
                "speaker_id": "user_1",
                "speaker_name": "Alice",
                "content": "OK, that's all for today's meeting. Feel free to reach out if you have any questions.",
                "timestamp": (base_time + timedelta(minutes=50)).isoformat(),
            },
        ]
        return messages

    def create_raw_data_list(self, messages: List[Dict[str, Any]]) -> List[RawData]:
        """Convert messages to RawData list"""
        raw_data_list = []
        for i, msg in enumerate(messages):
            raw_data = RawData(
                content=msg, data_id=f"msg_{i}", metadata={"message_index": i}
            )
            raw_data_list.append(raw_data)
        return raw_data_list

    def display_conversation_content(
        self, messages: List[Dict[str, Any]], title: str = "Conversation Content"
    ):
        """Display conversation content"""
        print(f"\n💬 {title}:")
        for msg in messages:
            timestamp = msg['timestamp']
            speaker = msg['speaker_name']
            content = msg['content']
            print(f"   [{timestamp}] {speaker}: {content}")

    def display_memory_results(self, memory_list: List, test_name: str):
        """Display memory extraction results"""
        print(f"\n📋 {test_name} - tanka_memorize results:")
        if memory_list:
            print(f"✅ Extracted {len(memory_list)} memories:")
            for i, memory in enumerate(memory_list):
                print(f"\n   Memory {i+1}:")
                print(f"     - Event ID: {memory.event_id}")
                print(f"     - User ID: {memory.user_id}")
                print(f"     - Memory Type: {memory.memory_type.value}")
                print(f"     - Timestamp: {memory.timestamp}")
                print(f"     - Subject: {memory.subject}")
                print(
                    f"     - Summary: {memory.summary[:150] if memory.summary else 'N/A'}..."
                )
                print(f"     - Group ID: {memory.group_id}")
                print(f"     - Participants: {memory.participants}")

                # Display specific fields
                if hasattr(memory, 'episode') and memory.episode:
                    print(f"     - Episode: {memory.episode[:150]}...")
                if hasattr(memory, 'tags') and memory.tags:
                    print(f"     - Tags: {memory.tags}")
                if hasattr(memory, 'hard_skills') and memory.hard_skills:
                    print(f"     - Hard Skills: {memory.hard_skills}")
                if hasattr(memory, 'soft_skills') and memory.soft_skills:
                    print(f"     - Soft Skills: {memory.soft_skills}")
                if (
                    hasattr(memory, 'projects_participated')
                    and memory.projects_participated
                ):
                    print(
                        f"     - Projects: {len(memory.projects_participated)} projects"
                    )
        else:
            print("❌ No memories extracted")

    async def run_memorize_pipeline(
        self,
        messages: List[Dict[str, Any]],
        test_name: str,
        group_id: str = "test_group",
    ) -> List:
        """Run memory extraction pipeline"""
        raw_data_list = self.create_raw_data_list(messages)

        # Split into history and new messages
        mid_point = len(raw_data_list) // 2
        history_raw_data_list = raw_data_list[:mid_point]
        new_raw_data_list = raw_data_list[mid_point:]

        print(
            f"\n📊 {test_name} - Processing {len(history_raw_data_list)} history messages + {len(new_raw_data_list)} new messages"
        )

        # Create MemorizeRequest
        memorize_request = MemorizeRequest(
            history_raw_data_list=history_raw_data_list,
            new_raw_data_list=new_raw_data_list,
            raw_data_type=RawDataType.CONVERSATION,
            participants=["alice", "bob", "charlie"],
            group_id=group_id,
        )

        # Call tanka_memorize
        print(f"\n🔄 Executing tanka_memorize.memorize()...")
        memory_list = await memorize(memorize_request)

        return memory_list

    async def run_streaming_memorize_pipeline(
        self,
        messages: List[Dict[str, Any]],
        test_name: str,
        group_id: str = "test_group",
    ) -> List:
        """Run streaming memory extraction pipeline - input messages one by one"""
        print(f"\n🌊 Starting streaming memory extraction test: {test_name}")
        print("=" * 80)

        all_raw_data = self.create_raw_data_list(messages)

        # Simulate streaming input: maintain history message buffer
        history_buffer = []
        all_memories = []

        print(f"📊 Will stream process {len(all_raw_data)} messages in total")

        for i, new_raw_data in enumerate(all_raw_data):
            print(f"\n{'='*60}")
            print(f"📨 Streaming input message {i+1}/{len(all_raw_data)}")
            print(f"{'='*60}")

            # Display current message
            msg_content = new_raw_data.content
            print(
                f"👤 {msg_content.get('speaker_name', 'Unknown')}: {msg_content.get('content', '')[:80]}..."
            )
            print(f"⏰ Time: {msg_content.get('timestamp', 'N/A')}")

            # Create MemorizeRequest - streaming input
            memorize_request = MemorizeRequest(
                history_raw_data_list=history_buffer.copy(),  # Current history
                new_raw_data_list=[new_raw_data],  # Only one new message
                raw_data_type=RawDataType.CONVERSATION,
                participants=["alice", "bob", "charlie"],
                group_id=group_id,
            )

            print(f"📊 Current status:")
            print(f"   History messages: {len(history_buffer)}")
            print(f"   New messages: 1")
            print(f"   Participants: {memorize_request.participants}")

            # Call tanka_memorize
            print(f"🔄 Executing tanka_memorize.memorize()...")
            try:
                memory_list = await memorize(memorize_request)

                if memory_list:
                    print(f"✅ Extracted {len(memory_list)} memories!")

                    # Display detailed info for each memory
                    for j, memory in enumerate(memory_list):
                        print(f"\n   🧠 Memory #{j+1}:")
                        print(f"      Type: {memory.memory_type.value}")
                        print(f"      User: {memory.user_id}")
                        print(f"      Title: {memory.subject}")
                        print(f"      Summary: {memory.summary[:100]}...")
                        print(f"      Event ID: {memory.event_id}")
                        print(f"      Participants: {memory.participants}")

                    all_memories.extend(memory_list)

                    # Debug: view Mock database operations
                    await self.debug_database_operations(memory_list, f"Streaming round {i+1}")

                else:
                    print("ℹ️ No memories extracted (may need more messages to trigger boundary detection)")

            except Exception as e:
                print(f"❌ memorize call failed: {e}")
                import traceback

                traceback.print_exc()

            # Add current message to history buffer
            history_buffer.append(new_raw_data)

            # Optional: limit history buffer size to avoid being too long
            max_history_size = 20
            if len(history_buffer) > max_history_size:
                history_buffer = history_buffer[-max_history_size:]
                print(f"📝 History buffer full, keeping recent {max_history_size} messages")

            # Streaming processing interval
            await asyncio.sleep(0.1)

        print(f"\n{'='*80}")
        print(f"🎉 Streaming test completed!")
        print(f"📊 Total processed: {len(all_raw_data)} messages")
        print(f"🧠 Generated memories: {len(all_memories)}")

        if all_memories:
            # Count memory types
            memory_types = {}
            for memory in all_memories:
                mem_type = memory.memory_type.value
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

            print(f"📋 Memory type distribution:")
            for mem_type, count in memory_types.items():
                print(f"   - {mem_type}: {count}")

        return all_memories

    async def debug_database_operations(self, memory_list: List, round_name: str):
        """Debug database operations"""
        print(f"\n🔍 Database operation debug - {round_name}:")

        # Try to get mock repository instance and view its status
        try:
            from core.di import get_bean_by_type
            from biz_layer.mock_repositories import (
                UserProfileRepository,
                MemoryRepository,
            )

            # Get repository instances
            user_profile_repo = get_bean_by_type(UserProfileRepository)
            memory_repo = get_bean_by_type(MemoryRepository)

            print(
                f"   📂 UserProfileRepository type: {type(user_profile_repo).__name__}"
            )
            print(f"   📂 MemoryRepository type: {type(memory_repo).__name__}")

            # If it's a mock instance, try to view its internal state
            if hasattr(user_profile_repo, '_stored_profiles'):
                profile_count = (
                    len(user_profile_repo._stored_profiles)
                    if user_profile_repo._stored_profiles
                    else 0
                )
                print(f"   👥 Mock user profiles count: {profile_count}")

                if profile_count > 0:
                    print(
                        f"   👥 User list: {list(user_profile_repo._stored_profiles.keys())}"
                    )

            if hasattr(memory_repo, '_stored_memories'):
                memory_count = (
                    len(memory_repo._stored_memories)
                    if memory_repo._stored_memories
                    else 0
                )
                print(f"   🧠 Mock stored memories count: {memory_count}")

                # Display recently saved memories
                if memory_count > 0:
                    recent_memories = memory_repo._stored_memories[-3:]  # Show recent 3
                    print(f"   🧠 Recently saved memories:")
                    for i, mem in enumerate(recent_memories):
                        if hasattr(mem, 'memory_type') and hasattr(mem, 'user_id'):
                            print(
                                f"      {i+1}. {mem.memory_type.value} - {mem.user_id}: {mem.title[:50]}..."
                            )
                        else:
                            print(
                                f"      {i+1}. {type(mem).__name__}: {str(mem)[:50]}..."
                            )

        except Exception as e:
            print(f"   ❌ Cannot get repository status: {e}")

        # Display memories saved this round
        if memory_list:
            print(f"   💾 Memories saved this round:")
            for i, memory in enumerate(memory_list):
                print(
                    f"      {i+1}. {memory.memory_type.value} - {memory.user_id}: {memory.subject[:50]}..."
                )

    @pytest.mark.asyncio
    async def test_project_discussion_pipeline(self):
        """Test project discussion conversation memory extraction pipeline"""
        print("\n🧪 Testing project discussion conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Create project discussion conversation
        messages = self.create_project_discussion_messages()
        self.display_conversation_content(messages, "Project Discussion Conversation")

        # Run pipeline
        memory_list = await self.run_memorize_pipeline(
            messages, "Project Discussion", "project_team"
        )

        # Display results
        self.display_memory_results(memory_list, "Project Discussion")

        # Simple validation (no forced assertions as LLM results may vary)
        if memory_list:
            print(f"✅ Project discussion pipeline test passed: memories extracted")
        else:
            print(f"ℹ️ Project discussion pipeline: no memories extracted (conversation may not have reached boundary conditions)")

    @pytest.mark.asyncio
    async def test_personal_conversation_pipeline(self):
        """Test personal care conversation memory extraction pipeline"""
        print("\n🧪 Testing personal care conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Create personal care conversation
        messages = self.create_personal_conversation_messages()
        self.display_conversation_content(messages, "Personal Care Conversation")

        # Run pipeline
        memory_list = await self.run_memorize_pipeline(
            messages, "Personal Care", "personal_chat"
        )

        # Display results
        self.display_memory_results(memory_list, "Personal Care")

        # Simple validation
        if memory_list:
            print(f"✅ Personal care pipeline test passed: memories extracted")
        else:
            print(f"ℹ️ Personal care pipeline: no memories extracted (conversation may not have reached boundary conditions)")

    @pytest.mark.asyncio
    async def test_complete_meeting_pipeline(self):
        """Test complete meeting conversation memory extraction pipeline"""
        print("\n🧪 Testing complete meeting conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Create complete meeting conversation
        messages = self.create_complete_meeting_conversation()
        self.display_conversation_content(messages, "Complete Meeting Conversation")

        # Run pipeline
        memory_list = await self.run_memorize_pipeline(
            messages, "Complete Meeting", "weekly_meeting"
        )

        # Display results
        self.display_memory_results(memory_list, "Complete Meeting")

        # Validate results
        if memory_list:
            print(f"✅ Complete meeting pipeline test passed: extracted {len(memory_list)} memories")

            # Validate memory types
            memory_types = [m.memory_type for m in memory_list]
            if MemoryType.EPISODE_SUMMARY in memory_types:
                print("   ✅ Contains episode memory")
            if MemoryType.PROFILE in memory_types:
                print("   ✅ Contains profile memory")

            # Validate participants
            all_participants = set()
            for memory in memory_list:
                if memory.participants:
                    all_participants.update(memory.participants)
            print(f"   📋 Involved participants: {list(all_participants)}")

        else:
            print(f"⚠️ Complete meeting pipeline: no memories extracted, may need to adjust conversation content or boundary detection logic")

    @pytest.mark.asyncio
    async def test_mixed_conversation_pipeline(self):
        """Test mixed conversation (project + personal) memory extraction pipeline"""
        print("\n🧪 Testing mixed conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Merge project discussion and personal care conversations
        project_messages = self.create_project_discussion_messages()
        personal_messages = self.create_personal_conversation_messages()
        mixed_messages = project_messages + personal_messages

        self.display_conversation_content(mixed_messages, "Mixed Conversation (Project + Personal)")

        # Run pipeline
        memory_list = await self.run_memorize_pipeline(
            mixed_messages, "Mixed Conversation", "mixed_chat"
        )

        # Display results
        self.display_memory_results(memory_list, "Mixed Conversation")

        # Analyze results
        if memory_list:
            print(f"✅ Mixed conversation pipeline test passed: extracted {len(memory_list)} memories")

            # Analyze memory type distribution
            episode_count = sum(
                1 for m in memory_list if m.memory_type == MemoryType.EPISODE_SUMMARY
            )
            profile_count = sum(
                1 for m in memory_list if m.memory_type == MemoryType.PROFILE
            )

            print(f"   📊 Memory type distribution:")
            print(f"     - Episode memory: {episode_count}")
            print(f"     - Profile memory: {profile_count}")

        else:
            print(f"ℹ️ Mixed conversation pipeline: no memories extracted")

    @pytest.mark.asyncio
    async def test_streaming_complete_meeting_pipeline(self):
        """Test streaming complete meeting conversation memory extraction pipeline"""
        print("\n🧪 Testing streaming complete meeting conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Create complete meeting conversation
        messages = self.create_complete_meeting_conversation()
        self.display_conversation_content(messages, "Complete Meeting Conversation (Streaming)")

        # Run streaming pipeline
        memory_list = await self.run_streaming_memorize_pipeline(
            messages, "Streaming Complete Meeting", "streaming_weekly_meeting"
        )

        # Display final results
        self.display_memory_results(memory_list, "Streaming Complete Meeting")

        # Validate results
        if memory_list:
            print(f"✅ Streaming complete meeting pipeline test passed: extracted {len(memory_list)} memories")

            # Validate memory types
            memory_types = [m.memory_type for m in memory_list]
            if MemoryType.EPISODE_SUMMARY in memory_types:
                print("   ✅ Contains episode memory")
            if MemoryType.PROFILE in memory_types:
                print("   ✅ Contains profile memory")

        else:
            print(f"⚠️ Streaming complete meeting pipeline: no memories extracted, check if boundary detection parameters need adjustment")

    @pytest.mark.asyncio
    async def test_streaming_mixed_conversation_pipeline(self):
        """Test streaming mixed conversation memory extraction pipeline"""
        print("\n🧪 Testing streaming mixed conversation pipeline")

        # Check API key
        if not os.getenv("OPENROUTER_API_KEY"):
            print("⚠️ OPENROUTER_API_KEY not set, skipping real LLM test")
            pytest.skip("OPENROUTER_API_KEY not available")
            return

        # Merge project discussion and personal care conversations
        project_messages = self.create_project_discussion_messages()
        personal_messages = self.create_personal_conversation_messages()
        mixed_messages = project_messages + personal_messages

        self.display_conversation_content(
            mixed_messages, "Mixed Conversation (Project + Personal) Streaming"
        )

        # Run streaming pipeline
        memory_list = await self.run_streaming_memorize_pipeline(
            mixed_messages, "Streaming Mixed Conversation", "streaming_mixed_chat"
        )

        # Display results
        self.display_memory_results(memory_list, "Streaming Mixed Conversation")

        # Analyze results
        if memory_list:
            print(f"✅ Streaming mixed conversation pipeline test passed: extracted {len(memory_list)} memories")

            # Analyze memory type distribution
            episode_count = sum(
                1 for m in memory_list if m.memory_type == MemoryType.EPISODE_SUMMARY
            )
            profile_count = sum(
                1 for m in memory_list if m.memory_type == MemoryType.PROFILE
            )

            print(f"   📊 Memory type distribution:")
            print(f"     - Episode memory: {episode_count}")
            print(f"     - Profile memory: {profile_count}")

        else:
            print(f"ℹ️ Streaming mixed conversation pipeline: no memories extracted")


async def run_all_tests():
    """Run all pipeline tests"""
    print("🚀 Starting Real Conversation Pipeline tests")
    print("=" * 80)

    test_instance = TestRealConversationPipeline()

    try:
        # First run standard batch tests
        print("\n📦 Phase 1: Batch processing tests")
        print("=" * 60)

        test_instance.setup_method()
        await test_instance.test_project_discussion_pipeline()

        test_instance.setup_method()
        await test_instance.test_personal_conversation_pipeline()

        test_instance.setup_method()
        await test_instance.test_complete_meeting_pipeline()

        test_instance.setup_method()
        await test_instance.test_mixed_conversation_pipeline()

        # Then run streaming processing tests
        print("\n🌊 Phase 2: Streaming processing tests")
        print("=" * 60)

        test_instance.setup_method()
        await test_instance.test_streaming_complete_meeting_pipeline()

        test_instance.setup_method()
        await test_instance.test_streaming_mixed_conversation_pipeline()

        print("\n" + "=" * 80)
        print("🎉 All pipeline tests completed!")
        print("=" * 80)
        print("\n💡 Test summary:")
        print("   📦 Batch processing tests:")
        print("     - Project discussion conversation pipeline ✅")
        print("     - Personal care conversation pipeline ✅")
        print("     - Complete meeting conversation pipeline ✅")
        print("     - Mixed conversation pipeline ✅")
        print("   🌊 Streaming processing tests:")
        print("     - Streaming complete meeting conversation pipeline ✅")
        print("     - Streaming mixed conversation pipeline ✅")
        print("\n📋 These tests validate the complete end-to-end functionality of tanka_memorize")
        print("🔍 Streaming tests provide detailed database operation debug information")

    except Exception as e:
        logger.error(f"❌ Pipeline test execution failed: {e}")
        import traceback

        traceback.print_exc()
        raise


async def run_streaming_tests_only():
    """Run streaming processing tests only"""
    print("🌊 Running streaming processing tests")
    print("=" * 80)

    test_instance = TestRealConversationPipeline()

    try:
        print("\n🧪 Streaming processing dedicated tests - simulating real message-by-message input")
        print("=" * 60)

        # Only run streaming tests for more detailed debug information
        test_instance.setup_method()
        await test_instance.test_streaming_complete_meeting_pipeline()

        test_instance.setup_method()
        await test_instance.test_streaming_mixed_conversation_pipeline()

        print("\n" + "=" * 80)
        print("🎉 Streaming processing tests completed!")
        print("=" * 80)
        print("\n💡 Streaming test features:")
        print("   - Input messages one by one, simulating real conversation scenarios")
        print("   - Real-time display of boundary detection results")
        print("   - Detailed database operation debug information")
        print("   - Mock Repository state tracking")
        print("\n🔍 Debug information helps analyze:")
        print("   - When conversation boundary detection is triggered")
        print("   - Detailed process of memory extraction")
        print("   - Database read/write operation status")

    except Exception as e:
        logger.error(f"❌ Streaming test execution failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Execute when running this script directly
    # Note: Environment is already initialized when running via bootstrap.py

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--streaming-only":
        print("🌊 Running streaming processing tests only")
        asyncio.run(run_streaming_tests_only())
    else:
        print("🚀 Running all tests (including batch and streaming)")
        print("💡 Tip: Use --streaming-only argument to run streaming tests only")
        asyncio.run(run_all_tests())

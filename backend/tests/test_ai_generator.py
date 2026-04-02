import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from ai_generator import AIGenerator


def make_text_response(text="Direct answer text"):
    """Fake Claude response with direct text answer."""
    content_block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(stop_reason="end_turn", content=[content_block])


def make_tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="tu_001"):
    """Fake Claude response requesting a tool call."""
    if tool_input is None:
        tool_input = {"query": "transformers"}
    tool_block = SimpleNamespace(
        type="tool_use",
        name=tool_name,
        input=tool_input,
        id=tool_id,
    )
    return SimpleNamespace(stop_reason="tool_use", content=[tool_block])


def make_final_text_response(text="Final synthesized answer"):
    return make_text_response(text)


class TestAIGeneratorDirectResponse(unittest.TestCase):
    """Verify: stop_reason != "tool_use" → returns content[0].text, one API call."""

    @patch("anthropic.Anthropic")
    def test_direct_response_returns_text(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response("Hello from Claude")

        gen = AIGenerator(api_key="test-key", model="claude-test")
        result = gen.generate_response(query="What is 2+2?")

        self.assertEqual(result, "Hello from Claude")

    @patch("anthropic.Anthropic")
    def test_direct_response_makes_exactly_one_api_call(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response()

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="General question")

        self.assertEqual(mock_client.messages.create.call_count, 1)

    @patch("anthropic.Anthropic")
    def test_tools_included_in_first_api_call(self, MockAnthropic):
        """tools list passed to generate_response() is forwarded in the API call."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response()

        tool_defs = [{"name": "search_course_content", "description": "...", "input_schema": {}}]

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="Find me something", tools=tool_defs)

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertIn("tools", call_kwargs)
        self.assertEqual(call_kwargs["tools"], tool_defs)

    @patch("anthropic.Anthropic")
    def test_no_tools_means_no_tools_key_in_call(self, MockAnthropic):
        """When tools=None, "tools" key is NOT added to the API params."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response()

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="General question", tools=None)

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertNotIn("tools", call_kwargs)


class TestAIGeneratorToolExecution(unittest.TestCase):
    """Verify: stop_reason == "tool_use" → tool is executed and second API call made."""

    @patch("anthropic.Anthropic")
    def test_tool_use_triggers_second_api_call(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        first_response = make_tool_use_response()
        second_response = make_final_text_response("Here is the answer")
        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Some tool result"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        result = gen.generate_response(
            query="What do transformers do?",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )

        self.assertEqual(mock_client.messages.create.call_count, 2)
        self.assertEqual(result, "Here is the answer")

    @patch("anthropic.Anthropic")
    def test_execute_tool_called_with_correct_name_and_inputs(self, MockAnthropic):
        """tool_manager.execute_tool() is called with correct tool name and unpacked inputs."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        tool_input = {"query": "what are neural networks", "course_name": "Deep Learning"}
        first_response = make_tool_use_response(
            tool_name="search_course_content",
            tool_input=tool_input,
            tool_id="tu_abc",
        )
        second_response = make_final_text_response()
        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result text"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="...", tools=[{}], tool_manager=tool_manager)

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="what are neural networks",
            course_name="Deep Learning",
        )

    @patch("anthropic.Anthropic")
    def test_tool_result_included_in_second_api_call_messages(self, MockAnthropic):
        """Second API call includes tool result as tool_result block with matching tool_use_id.

        This verifies that even error strings (from the broken search path)
        are faithfully passed back to Claude.
        """
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        first_response = make_tool_use_response(tool_id="tu_xyz", tool_input={"query": "q"})
        second_response = make_final_text_response()
        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Search error: n_results must be a positive integer"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="...", tools=[{}], tool_manager=tool_manager)

        second_call_kwargs = mock_client.messages.create.call_args[1]
        messages = second_call_kwargs["messages"]
        last_message = messages[-1]
        self.assertEqual(last_message["role"], "user")
        tool_result_block = last_message["content"][0]
        self.assertEqual(tool_result_block["type"], "tool_result")
        self.assertEqual(tool_result_block["tool_use_id"], "tu_xyz")
        self.assertEqual(
            tool_result_block["content"],
            "Search error: n_results must be a positive integer",
        )

    @patch("anthropic.Anthropic")
    def test_single_round_follow_up_call_includes_tools(self, MockAnthropic):
        """After one tool round, the follow-up API call includes tools (second round still available)."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        first_response = make_tool_use_response()
        second_response = make_final_text_response()
        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool output"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="...", tools=[{"name": "t"}], tool_manager=tool_manager)

        second_call_kwargs = mock_client.messages.create.call_args[1]
        self.assertIn("tools", second_call_kwargs)

    @patch("anthropic.Anthropic")
    def test_conversation_history_included_in_system_prompt(self, MockAnthropic):
        """conversation_history is appended to the system prompt in the first API call."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response()

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(
            query="Follow-up question",
            conversation_history="User: Hello\nAssistant: Hi there",
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertIn("Previous conversation:", call_kwargs["system"])
        self.assertIn("User: Hello", call_kwargs["system"])


class TestAIGeneratorTwoRoundToolExecution(unittest.TestCase):
    """Verify: sequential tool calls up to 2 rounds with correct API call counts and message accumulation."""

    @patch("anthropic.Anthropic")
    def test_two_round_tool_use_happy_path(self, MockAnthropic):
        """2 tool rounds → 3 API calls, tool executed twice, final text from call 3 returned."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response(tool_id="tu_1", tool_input={"query": "outline"})
        r2 = make_tool_use_response(tool_name="search_course_content", tool_id="tu_2", tool_input={"query": "topic"})
        r3 = make_final_text_response("Complete synthesized answer")
        mock_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool result"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        result = gen.generate_response(
            query="Find a course on the same topic as lesson 4",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )

        self.assertEqual(mock_client.messages.create.call_count, 3)
        self.assertEqual(tool_manager.execute_tool.call_count, 2)
        self.assertEqual(result, "Complete synthesized answer")

    @patch("anthropic.Anthropic")
    def test_round_one_api_call_includes_tools(self, MockAnthropic):
        """After round 1 tool execution, the second API call includes tools (round 2 still available)."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response(tool_id="tu_1")
        r2 = make_tool_use_response(tool_id="tu_2")
        r3 = make_final_text_response()
        mock_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        tools = [{"name": "search_course_content"}]
        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="...", tools=tools, tool_manager=tool_manager)

        # call_args_list[1] is the second API call (after round 1)
        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        self.assertIn("tools", second_call_kwargs)

    @patch("anthropic.Anthropic")
    def test_round_two_synthesis_call_excludes_tools(self, MockAnthropic):
        """After round 2 tool execution, the third (synthesis) API call excludes tools."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response(tool_id="tu_1")
        r2 = make_tool_use_response(tool_id="tu_2")
        r3 = make_final_text_response()
        mock_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="...", tools=[{"name": "t"}], tool_manager=tool_manager)

        # call_args_list[2] is the third API call (synthesis after round 2)
        third_call_kwargs = mock_client.messages.create.call_args_list[2][1]
        self.assertNotIn("tools", third_call_kwargs)

    @patch("anthropic.Anthropic")
    def test_message_accumulation_two_rounds(self, MockAnthropic):
        """Third API call messages contain: user, asst+tool_use r1, tool_result r1, asst+tool_use r2, tool_result r2."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response(tool_id="tu_1", tool_input={"query": "q1"})
        r2 = make_tool_use_response(tool_id="tu_2", tool_input={"query": "q2"})
        r3 = make_final_text_response()
        mock_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = ["result_1", "result_2"]

        gen = AIGenerator(api_key="test-key", model="claude-test")
        gen.generate_response(query="Multi-step query", tools=[{"name": "t"}], tool_manager=tool_manager)

        third_call_kwargs = mock_client.messages.create.call_args_list[2][1]
        messages = third_call_kwargs["messages"]

        # 5 messages: user query, asst r1, tool_result r1, asst r2, tool_result r2
        self.assertEqual(len(messages), 5)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"][0]["tool_use_id"], "tu_1")
        self.assertEqual(messages[2]["content"][0]["content"], "result_1")
        self.assertEqual(messages[3]["role"], "assistant")
        self.assertEqual(messages[4]["role"], "user")
        self.assertEqual(messages[4]["content"][0]["tool_use_id"], "tu_2")
        self.assertEqual(messages[4]["content"][0]["content"], "result_2")

    @patch("anthropic.Anthropic")
    def test_tool_execution_exception_triggers_graceful_synthesis(self, MockAnthropic):
        """If execute_tool raises, a synthesis call is made without tools and no exception propagates."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response(tool_id="tu_err")
        synthesis = make_final_text_response("Sorry, I encountered an error")
        mock_client.messages.create.side_effect = [r1, synthesis]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = Exception("connection timeout")

        gen = AIGenerator(api_key="test-key", model="claude-test")
        result = gen.generate_response(query="...", tools=[{"name": "t"}], tool_manager=tool_manager)

        self.assertEqual(mock_client.messages.create.call_count, 2)
        synthesis_kwargs = mock_client.messages.create.call_args[1]
        self.assertNotIn("tools", synthesis_kwargs)
        self.assertEqual(result, "Sorry, I encountered an error")

    @patch("anthropic.Anthropic")
    def test_natural_termination_after_one_round_no_extra_call(self, MockAnthropic):
        """When Claude returns text (not tool_use) after round 1, no extra API call is made."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        r1 = make_tool_use_response()
        r2 = make_final_text_response("Done after one round")
        mock_client.messages.create.side_effect = [r1, r2]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        gen = AIGenerator(api_key="test-key", model="claude-test")
        result = gen.generate_response(query="...", tools=[{"name": "t"}], tool_manager=tool_manager)

        self.assertEqual(mock_client.messages.create.call_count, 2)
        self.assertEqual(result, "Done after one round")


if __name__ == "__main__":
    unittest.main()

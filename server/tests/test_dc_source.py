"""Tests for data-flow source matching and member/score extraction."""
from __future__ import annotations

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.collections import DataCollection
from server.models.project import Project
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tests.dc_test_helpers import create_agent, create_task, create_session, create_completed_call
from server.tasks.tick_scheduler import _check_agent_pattern, _matches_data_flow_source, _extract_member, _extract_score
from server.tests.test_reporter import TestReport


class CheckAgentPatternTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def test_exact_match(self):
        self.assertTrue(_check_agent_pattern("agentFoo", "agentFoo"))
        self.report.add("test_exact_match", "PASS",
            "Exact string matching works for agent name patterns.")

    def test_exact_no_match(self):
        self.assertFalse(_check_agent_pattern("agentFoo", "agentBar"))
        self.report.add("test_exact_no_match", "PASS",
            "Different names are correctly rejected.")

    def test_wildcard_match_all(self):
        self.assertTrue(_check_agent_pattern("anything", "*"))
        self.report.add("test_wildcard_match_all", "PASS",
            "Single-asterisk wildcard matches any string — used for 'all agents'.")

    def test_wildcard_suffix(self):
        self.assertTrue(_check_agent_pattern("someAgent", "some*"))
        self.report.add("test_wildcard_suffix", "PASS",
            "Suffix wildcard (prefix*) matches strings starting with the prefix.")

    def test_wildcard_prefix(self):
        self.assertTrue(_check_agent_pattern("testAgent", "*Agent"))
        self.report.add("test_wildcard_prefix", "PASS",
            "Prefix wildcard (*suffix) matches strings ending with the suffix.")

    def test_wildcard_middle(self):
        self.assertTrue(_check_agent_pattern("abc123def", "abc*def"))
        self.report.add("test_wildcard_middle", "PASS",
            "Wildcard in middle matches strings that start and end with the given patterns.")

    def test_wildcard_no_match(self):
        self.assertFalse(_check_agent_pattern("other", "some*"))
        self.report.add("test_wildcard_no_match", "PASS",
            "Wildcard correctly rejects non-matching inputs.")

    def test_empty_pattern(self):
        self.assertFalse(_check_agent_pattern("anything", ""))
        self.report.add("test_empty_pattern", "PASS",
            "Empty pattern returns False as it cannot match anything.")


class MatchesDataFlowSourceTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.agent, self.av = create_agent("test-agent")
        self.task = create_task("test-func", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)
        self.call = create_completed_call(self.agent, self.task, self.session, self.sv)

    def test_match_agent_and_function(self):
        source = {"type": "query", "agent": ["test-agent"], "function": ["test-func"]}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_match_agent_and_function", "PASS",
            "Query source matches when both agent and function globs match the call's properties.")

    def test_match_agent_glob(self):
        source = {"type": "query", "agent": ["test-*"], "function": ["test-func"]}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_match_agent_glob", "PASS",
            "Agent patterns support glob matching (test-* matches test-agent).")

    def test_no_match_agent(self):
        source = {"type": "query", "agent": ["other-agent"], "function": ["test-func"]}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_no_match_agent", "PASS",
            "Non-matching agent pattern correctly rejects the call.")

    def test_no_match_function(self):
        source = {"type": "query", "agent": ["test-agent"], "function": ["other-func"]}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_no_match_function", "PASS",
            "Non-matching function pattern correctly rejects the call.")

    def test_match_session(self):
        source = {"type": "query", "agent": ["test-agent"], "function": ["test-func"], "session": ["test-session"]}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_match_session", "PASS",
            "Session pattern matching works when call's session name matches.")

    def test_no_match_session(self):
        source = {"type": "query", "agent": ["test-agent"], "function": ["test-func"], "session": ["wrong-session"]}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_no_match_session", "PASS",
            "Non-matching session pattern correctly rejects the call.")

    def test_wildcard_agent(self):
        source = {"type": "query", "agent": ["*"], "function": ["test-func"]}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_wildcard_agent", "PASS",
            "Wildcard agent (*) matches any agent name.")

    def test_multiple_agent_patterns_any_match(self):
        source = {"type": "query", "agent": ["no-match", "test-agent", "also-no"], "function": ["test-func"]}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_multiple_agent_patterns_any_match", "PASS",
            "When multiple agent patterns are given, any single match is sufficient (OR logic).")

    def test_no_patterns_match_anything(self):
        source = {"type": "query"}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_no_patterns_match_anything", "PASS",
            "A source definition with no agent/function patterns matches all completed calls.")

    def test_stream_type_handled_by_propagation(self):
        """Stream sources are handled by _propagate_from_collections, not direct matching."""
        source = {"type": "stream", "stream": "my.stream"}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_stream_type_handled_by_propagation", "PASS",
            "Stream-type sources return False from _matches_data_flow_source because "
            "they are handled by _propagate_from_collections instead.")

    def test_set_type_handled_by_propagation(self):
        """Set sources are handled by _propagate_from_collections, not direct matching."""
        source = {"type": "set", "set": "my.set"}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_set_type_handled_by_propagation", "PASS",
            "Set-type sources return False from _matches_data_flow_source because "
            "they are handled by _propagate_from_collections instead.")

    def test_unknown_type_returns_false(self):
        source = {"type": "unknown"}
        self.assertFalse(_matches_data_flow_source(self.call, source))
        self.report.add("test_unknown_type_returns_false", "PASS",
            "Unknown source types are safely rejected with False.")

    def test_string_pattern_instead_of_list(self):
        source = {"type": "query", "agent": "test-agent", "function": "test-func"}
        self.assertTrue(_matches_data_flow_source(self.call, source))
        self.report.add("test_string_pattern_instead_of_list", "PASS",
            "Single string patterns work in addition to list patterns. The code wraps single strings in a list.")

    def test_no_match_project(self):
        proj = Project.objects.create(name="other-project")
        agent, av = create_agent("project-agent")
        td = create_task("project-func", agent=agent)
        AgentModel.objects.filter(pk=agent.pk).update(parent_project=proj)
        agent.refresh_from_db()
        session, sv = create_session(agent, av)
        call = create_completed_call(agent, td, session, sv)
        source = {"type": "query", "project": "wrong-project", "agent": ["project-agent"]}
        self.assertFalse(_matches_data_flow_source(call, source))
        self.report.add("test_no_match_project", "PASS",
            "Non-matching project filter correctly rejects calls from other projects.")

    def test_match_project(self):
        proj = Project.objects.create(name="right-project")
        agent, av = create_agent("project-match-agent")
        td = create_task("project-func", agent=agent)
        AgentModel.objects.filter(pk=agent.pk).update(parent_project=proj)
        agent.refresh_from_db()
        session, sv = create_session(agent, av)
        call = create_completed_call(agent, td, session, sv)
        source = {"type": "query", "project": "right-project", "agent": ["project-match-agent"]}
        self.assertTrue(_matches_data_flow_source(call, source))
        self.report.add("test_match_project", "PASS",
            "Project filter correctly matches calls belonging to the specified project.")


class ExtractMemberTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.flow = DataCollection.objects.create(name="extract-test.stream", collection_type="stream")
        self.agent, self.av = create_agent("extract-agent")
        self.td = create_task("extract-func", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)
        self.call = create_completed_call(self.agent, self.td, self.session, self.sv, carguments={"msg": "hello"})

    def test_stream_returns_hash(self):
        member = _extract_member(self.flow, self.call, self.call)
        self.assertEqual(len(member), 32)
        self.assertIsInstance(member, str)
        self.report.add("test_stream_returns_hash", "PASS",
            "Streams auto-generate a 32-character SHA-256 hex digest as member. "
            "This provides content-addressed dedup based on arguments+timestamp.")

    def test_stream_hash_deterministic(self):
        m1 = _extract_member(self.flow, self.call, self.call)
        m2 = _extract_member(self.flow, self.call, self.call)
        self.assertEqual(m1, m2)
        self.report.add("test_stream_hash_deterministic", "PASS",
            "The hash is deterministic — identical inputs produce identical members. "
            "Ensures dedup works correctly.")

    def test_set_returns_str_pk_when_no_expr(self):
        self.flow.collection_type = "set"
        self.flow.member_field = ""
        member = _extract_member(self.flow, self.call, self.call)
        self.assertEqual(member, str(self.call.pk))
        self.report.add("test_set_returns_str_pk_when_no_expr", "PASS",
            "Sets fall back to the AgentTaskCall PK as member when no member_field expression is configured.")

    def test_set_uses_expr(self):
        self.flow.collection_type = "set"
        self.flow.member_field = "item.get('msg', 'fallback')"
        member = _extract_member(self.flow, self.call, self.call)
        self.assertEqual(member, "hello")
        self.report.add("test_set_uses_expr", "PASS",
            "Sets evaluate the member_field Python expression against the item value. "
            "Here 'msg' is extracted from {'msg': 'hello'}.")

    def test_set_expr_error_falls_back_to_pk(self):
        self.flow.collection_type = "set"
        self.flow.member_field = "item.nonexistent + 1"
        member = _extract_member(self.flow, self.call, self.call)
        self.assertEqual(member, str(self.call.pk))
        self.report.add("test_set_expr_error_falls_back_to_pk", "PASS",
            "When the member_field expression raises an exception (undefined attribute), "
            "the code gracefully falls back to the call PK instead of crashing.")


class ExtractScoreTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.flow = DataCollection.objects.create(name="score-test.stream", collection_type="stream")
        self.agent, self.av = create_agent("score-agent")
        self.td = create_task("score-func", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)
        self.call = create_completed_call(self.agent, self.td, self.session, self.sv, carguments={"ts": 12345.0})

    def test_stream_returns_timestamp(self):
        score = _extract_score(self.flow, self.call, self.call)
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)
        self.report.add("test_stream_returns_timestamp", "PASS",
            "Streams auto-generate a Unix timestamp as score, ensuring "
            "items are ordered by creation time by default.")

    def test_set_returns_float_from_expr(self):
        self.flow.collection_type = "set"
        self.flow.score_field = "item.get('ts', 0)"
        score = _extract_score(self.flow, self.call, self.call)
        self.assertEqual(score, 12345.0)
        self.report.add("test_set_returns_float_from_expr", "PASS",
            "Sets evaluate the score_field expression to produce a float score. "
            "Here 'ts' is extracted from the arguments.")

    def test_set_no_expr_returns_timestamp(self):
        self.flow.collection_type = "set"
        self.flow.score_field = ""
        score = _extract_score(self.flow, self.call, self.call)
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)
        self.report.add("test_set_no_expr_returns_timestamp", "PASS",
            "When no score_field expression is configured, sets also fall back to timestamp.")

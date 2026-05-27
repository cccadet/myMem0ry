"""Tests for auth.py — Bearer token, host allowlisting, CORS."""

from __future__ import annotations

from mem0ry.auth import check_bearer, check_host, parse_allowed_hosts


def test_check_bearer_no_token_configured() -> None:
    assert check_bearer("anything", None) is True


def test_check_bearer_no_token_provided() -> None:
    assert check_bearer(None, "secret") is False


def test_check_bearer_empty_string() -> None:
    assert check_bearer("", "secret") is False


def test_check_bearer_correct_token() -> None:
    assert check_bearer("Bearer secret", "secret") is True


def test_check_bearer_token_without_prefix() -> None:
    assert check_bearer("secret", "secret") is True


def test_check_bearer_wrong_token() -> None:
    assert check_bearer("Bearer wrong", "secret") is False


def test_check_host_empty_allowlist() -> None:
    assert check_host("evil.com", set()) is True


def test_check_host_no_header() -> None:
    assert check_host(None, {"localhost"}) is False


def test_check_host_exact_match() -> None:
    assert check_host("localhost", {"localhost"}) is True


def test_check_host_with_port() -> None:
    assert check_host("localhost:8080", {"localhost"}) is True


def test_check_host_blocked() -> None:
    assert check_host("evil.com", {"localhost", "127.0.0.1"}) is False


def test_check_host_ip_match() -> None:
    assert check_host("127.0.0.1", {"127.0.0.1"}) is True


def test_parse_allowed_hosts_empty() -> None:
    assert parse_allowed_hosts("") == set()


def test_parse_allowed_hosts_single() -> None:
    assert parse_allowed_hosts("localhost") == {"localhost"}


def test_parse_allowed_hosts_multiple() -> None:
    result = parse_allowed_hosts("localhost, 127.0.0.1, example.com")
    assert result == {"localhost", "127.0.0.1", "example.com"}


def test_parse_allowed_hosts_strips_whitespace() -> None:
    result = parse_allowed_hosts("  localhost  ,  127.0.0.1  ")
    assert result == {"localhost", "127.0.0.1"}

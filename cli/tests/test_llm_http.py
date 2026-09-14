from agent.deepagents_runtime.llm_http import install_stable_tls_httpx


def test_install_stable_tls_httpx_disables_keepalive():
    install_stable_tls_httpx()
    install_stable_tls_httpx()  # idempotent
    import httpx

    client = httpx.Client()
    try:
        pool = client._transport._pool
        assert pool._max_keepalive_connections == 0
        assert pool._local_address in {None, "0.0.0.0"}
    finally:
        client.close()

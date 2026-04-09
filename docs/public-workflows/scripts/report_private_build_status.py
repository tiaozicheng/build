import argparse
import json
import urllib.error
import urllib.request


def post_status(
    source_repo: str,
    source_sha: str,
    token: str,
    state: str,
    context: str,
    description: str,
    target_url: str,
) -> None:
    if "/" not in source_repo:
        raise SystemExit(f"非法 source_repo：{source_repo}")

    payload = {
        "state": state,
        "context": context,
    }
    if description:
        payload["description"] = description[:140]
    if target_url:
        payload["target_url"] = target_url

    request = urllib.request.Request(
        url=f"https://api.github.com/repos/{source_repo}/statuses/{source_sha}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "Content-Type": "application/json",
            "User-Agent": "public-build-status-reporter",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            if response.status // 100 != 2:
                raise SystemExit(f"状态回写失败，HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"状态回写失败，HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Report public build status back to the private source commit.")
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--state", required=True, choices=["pending", "success", "failure", "error"])
    parser.add_argument("--context", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--target-url", default="")
    args = parser.parse_args()

    post_status(
        source_repo=args.source_repo,
        source_sha=args.source_sha,
        token=args.token,
        state=args.state,
        context=args.context,
        description=args.description,
        target_url=args.target_url,
    )


if __name__ == "__main__":
    main()

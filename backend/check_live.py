"""List Live API candidates without generating content or exposing credentials."""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone


def live_candidates(client):
    candidates = []
    for model in client.models.list():
        actions = model.supported_actions or []
        if any('bidigeneratecontent' in action.lower() for action in actions):
            candidates.append(model.name)
    return sorted(name for name in candidates if name)


async def check_connection(client, model):
    async def connect():
        async with client.aio.live.connect(
            model=model,
            config={'response_modalities': ['AUDIO']},
        ):
            pass
    await asyncio.wait_for(connect(), timeout=20)


def check_ephemeral(key, model):
    from google import genai
    from google.genai import types
    from app.voice import mint_token
    token = mint_token(key, model, {'test': 'Synthetic read-only connection test; no real project data'},
                       datetime.now(timezone.utc))
    with genai.Client(api_key=token, vertexai=False, http_options=types.HttpOptions(
        api_version='v1alpha', timeout=30000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )) as client:
        asyncio.run(check_connection(client, model))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-stdin', action='store_true',
                        help='Read the key from a private pipe rather than environment variables')
    tests = parser.add_mutually_exclusive_group()
    tests.add_argument('--connect-test', action='store_true',
                        help='Explicitly open and close one Live session without sending content')
    tests.add_argument('--ephemeral-test', action='store_true',
                       help='Explicitly test a constrained ephemeral token using synthetic context only')
    parser.add_argument('--model', default='gemini-3.8-live',
                        help='Live model to test (default: gemini-3.8-live)')
    args = parser.parse_args(argv)
    key = (sys.stdin.read().strip() if args.key_stdin else
           (os.getenv('KATALYST_LIVE_API_KEY') or os.getenv('GOOGLE_API_KEY') or
            os.getenv('GEMINI_API_KEY') or '').strip())
    if not key:
        print('No API key supplied. No request was sent.', file=sys.stderr)
        return 1

    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    from httpx import HTTPError
    from websockets.exceptions import WebSocketException
    from fastapi import HTTPException
    try:
        with genai.Client(
            api_key=key, vertexai=False,
            http_options=types.HttpOptions(
                timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)),
        ) as client:
            candidates = live_candidates(client)
            if args.connect_test or args.ephemeral_test:
                model = args.model.removeprefix('models/')
                if 'models/' + model not in candidates:
                    print('Selected model does not advertise Live support for this key.',
                          file=sys.stderr)
                    return 1
                if args.ephemeral_test:
                    check_ephemeral(key, model)
                else:
                    asyncio.run(check_connection(client, model))
    except HTTPException as exc:
        print(str(exc.detail), file=sys.stderr)
        return 1
    except APIError as exc:
        hints = {
            400: 'Check API-key configuration.',
            401: 'Check API-key authentication.',
            402: 'Check the key project billing tier and prepaid credit status.',
            403: 'Check API-key restrictions and service permissions.',
            429: 'Quota or rate limit reached. Do not repeatedly retry.',
        }
        print(f'Google model discovery failed (HTTP {exc.code}). ' +
              hints.get(exc.code, 'Check Google AI Studio service status and access.'),
              file=sys.stderr)
        return 1
    except (HTTPError, OSError, TimeoutError):
        print('Model discovery could not connect or timed out. No automatic retry was made.',
              file=sys.stderr)
        return 1
    except WebSocketException:
        print('Live connection was rejected or closed. Check the selected model quota, '
              'free-tier eligibility, billing status and Live API access in AI Studio. '
              'No automatic retry was made. Upstream details omitted to protect credentials.',
              file=sys.stderr)
        return 1

    if not candidates:
        print('No models advertising bidiGenerateContent were returned for this key.',
              file=sys.stderr)
        return 1
    print('Models advertising Live API support:')
    for name in candidates:
        print('  ' + name)
    if args.connect_test or args.ephemeral_test:
        if args.ephemeral_test:
            print('Constrained ephemeral-token connection accepted and closed: ' + args.model)
            print('Only synthetic test instructions were used. No audio or actual project data was sent.')
        else:
            print('Live connection accepted and closed: ' + args.model)
            print('No audio, text prompts, project data, or ephemeral tokens were sent.')
        print('Connection success does not yet verify audio replies or tool calling.')
        return 0
    print('Discovery only: no audio, project data, generation, or ephemeral tokens were sent.')
    print('A listing does not prove free-tier eligibility, available quota, or session access.')
    print('Next: verify candidate pricing, then explicitly test a short Live connection.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

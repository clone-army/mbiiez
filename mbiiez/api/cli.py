import argparse
import json
import os
from . import keys


def main(argv):
    parser = argparse.ArgumentParser(prog='mbii api')
    commands = parser.add_subparsers(dest='command', required=True)
    gen = commands.add_parser('keygen', help='Print a new service key once')
    gen.add_argument('--scope', choices=keys.ROLES, default='admin')
    gen.add_argument('--label', default='web')
    commands.add_parser('keys', help='List key metadata, never secrets')
    rev = commands.add_parser('revoke')
    rev.add_argument('id')
    serve = commands.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8081)
    args = parser.parse_args(argv)
    if args.command == 'keygen':
        _, token = keys.generate(args.scope, args.label)
        print(token)
    elif args.command == 'keys':
        print(json.dumps(keys.listing(), indent=2))
    elif args.command == 'revoke':
        keys.revoke(args.id)
    else:
        from waitress import serve
        from .server import create_app
        from .shared_node import start
        os.environ['MBIIEZ_API_PORT']=str(args.port)
        start()
        serve(create_app(), host=args.host, port=args.port, threads=8,
              max_request_body_size=2 * 1024 * 1024)

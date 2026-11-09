"""Real fixed-Bun TLS gate; ephemeral CA and loopback only, no TLS bypass."""
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    env = {k: v for k, v in os.environ.items() if k not in (
        'NODE_EXTRA_CA_CERTS', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_OPTIONS', 'BUN_OPTIONS',
        'NODE_TLS_REJECT_UNAUTHORIZED', 'NODE_USE_SYSTEM_CA', 'HTTP_PROXY', 'HTTPS_PROXY',
        'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy')}
    with tempfile.TemporaryDirectory(prefix='andcode-ca-tls-') as tmp:
        root = Path(tmp)
        def openssl(*args):
            subprocess.run(['openssl', *args], cwd=root, check=True, capture_output=True, timeout=30)
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem',
                '-days', '1', '-subj', '/CN=Ephemeral andcode test CA', '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.csr',
                '-subj', '/CN=localhost')
        (root / 'extensions').write_text('subjectAltName=DNS:localhost\nbasicConstraints=CA:FALSE\n'
                                       'keyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
        openssl('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial',
                '-out', 'server.pem', '-days', '1', '-extfile', 'extensions')
        (root / 'server.mjs').write_text('''const s=Bun.serve({hostname:"127.0.0.1",port:0,
tls:{key:Bun.file("server.key"),cert:Bun.file("server.pem")},fetch:()=>new Response("tls-ok")});
console.log(s.port);''')
        (root / 'client.mjs').write_text('''import {rootCertificates} from "node:tls";
if(rootCertificates.length<100)throw new Error("Bundled roots missing");
try { const r=await fetch(process.argv[2],{signal:AbortSignal.timeout(5000)});
if(await r.text()!=="tls-ok")throw new Error("Unexpected body");console.log("TLS_ACCEPTED");
}catch(error){console.log("TLS_REJECTED:"+error.code)}''')
        server = subprocess.Popen(['bun', 'server.mjs'], cwd=root, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Bun startup is bounded externally by CI step timeout.
            port = int(server.stdout.readline().strip())
            cases = [('disabled', 'localhost', False, False),
                     ('enabled', 'localhost', True, True),
                     ('hostname-mismatch', '127.0.0.1', True, False),
                     ('disabled-again', 'localhost', False, False)]
            for name, host, enabled, accept in cases:
                child_env = dict(env)
                if enabled:
                    child_env['NODE_EXTRA_CA_CERTS'] = str(root / 'ca.pem')
                result = subprocess.run(['bun', 'client.mjs', f'https://{host}:{port}'],
                                        cwd=root, env=child_env, check=True, capture_output=True,
                                        text=True, timeout=15)
                expected = 'TLS_ACCEPTED' if accept else 'TLS_REJECTED:'
                if expected not in result.stdout:
                    raise AssertionError(name + ': ' + result.stdout + result.stderr)
                if not accept and not any(code in result.stdout for code in (
                    'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
                    'SELF_SIGNED_CERT_IN_CHAIN', 'CERT_ALTNAME_INVALID', 'ERR_TLS_CERT_ALTNAME_INVALID')):
                    raise AssertionError('Not a certificate rejection: ' + result.stdout)
                if name == 'hostname-mismatch' and 'CERT_ALTNAME_INVALID' not in result.stdout:
                    raise AssertionError('Expected hostname rejection: ' + result.stdout)
                print(name + ': ' + result.stdout.strip())
        finally:
            server.terminate()
            try:
                server.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate(timeout=5)


if __name__ == '__main__':
    main()

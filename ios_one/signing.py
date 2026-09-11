"""Read Team IDs from public certificate subjects, never from display-name suffixes."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import ssl
import tempfile


@dataclass(frozen=True)
class SigningCertificate:
    fingerprint: str
    common_name: str
    team_id: str
    organization: str = ''

def development_identities(output):
    """Fingerprint -> CN for valid development identities reported by security -v."""
    return {match.group(1).upper(): match.group(2) for match in re.finditer(
        r'^\s*\d+\)\s+([A-Fa-f0-9]{40})\s+"((?:Apple Development|iPhone Developer):[^"\n]+)"',
        output, re.MULTILINE)}


def certificate_subject(output):
    """OpenSSL RFC2253 with sep_multiline keeps escaped DN values on one line."""
    teams = set(re.findall(r'^\s*OU\s*=\s*([A-Z0-9]{10})\s*$', output, re.MULTILINE))
    organizations = re.findall(r'^\s*O\s*=\s*(.*?)\s*$', output, re.MULTILINE)
    return (next(iter(teams)) if len(teams) == 1 else None,
            organizations[0] if len(organizations) == 1 else '')


def discover_certificates(runner):
    identities = development_identities(runner.run(
        ['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning'],
        'signing-identities', check=False, timeout=30))
    certificates = {}
    for index, common_name in enumerate(sorted(set(identities.values())), 1):
        # find-certificate reads public certificates. No key export or keychain mutation.
        output = runner.run(['/usr/bin/security', 'find-certificate', '-a', '-c', common_name, '-p'],
                            'signing-certificates-' + str(index), check=False, timeout=30)
        for pem in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', output, re.DOTALL):
            try:
                der = ssl.PEM_cert_to_DER_cert(pem)
            except ValueError:
                continue
            # SHA-1 is the identity handle printed by security, not a trust decision.
            fingerprint = hashlib.sha1(der).hexdigest().upper()
            if fingerprint not in identities or fingerprint in certificates:
                continue
            with tempfile.TemporaryDirectory(prefix='ios-one-public-certificate-') as folder:
                file = Path(folder) / 'certificate.pem'
                file.write_text(pem + '\n', encoding='ascii')
                file.chmod(0o600)
                subject = runner.run(['/usr/bin/openssl', 'x509', '-in', file, '-noout', '-subject',
                                      '-nameopt', 'RFC2253,sep_multiline'],
                                     'signing-subject-' + fingerprint[:12], check=False, timeout=30)
            team_id, organization = certificate_subject(subject)
            if team_id:
                certificates[fingerprint] = SigningCertificate(fingerprint, identities[fingerprint], team_id, organization)
    return sorted(certificates.values(), key=lambda item: (item.team_id, item.fingerprint))


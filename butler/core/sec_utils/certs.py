import os
import datetime
import logging
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from butler.core.constants import DATA_DIR

logger = logging.getLogger("CertGenerator")

CERTS_DIR = DATA_DIR / "system_data" / "certs"
CERT_FILE = CERTS_DIR / "cert.pem"
KEY_FILE = CERTS_DIR / "key.pem"

def generate_self_signed_cert(force: bool = False) -> tuple[Path, Path]:
    """
    Generates a high-strength self-signed RSA-4096 certificate for SSL/TLS if it doesn't exist.
    Returns:
        tuple[Path, Path]: (cert_path, key_path)
    """
    if CERT_FILE.exists() and KEY_FILE.exists() and not force:
        logger.info(f"Existing SSL certificates found at {CERTS_DIR}.")
        return CERT_FILE, KEY_FILE

    logger.info("Generating new self-signed RSA-4096 certificate for secure local communications...")
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate Private Key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096
    )

    # 2. Setup Subject and Issuer names
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Butler"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    # 3. Setup SAN (Subject Alternative Name)
    alt_names = [
        x509.DNSName("localhost"),
        x509.DNSName("butler.local"),
        x509.IPAddress(datetime.datetime.strptime("127.0.0.1", "%d.%m.%Y")), # Dummy but let's use dns or correct IP formatting
    ]
    # Correct way to create IP SANs:
    import ipaddress
    alt_names = [
        x509.DNSName("localhost"),
        x509.DNSName("butler.local"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
    ]

    # 4. Build Certificate
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650)) # 10 years validity
        .add_extension(
            x509.SubjectAlternativeName(alt_names),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # 5. Write Private Key
    with open(KEY_FILE, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    # 6. Write Certificate
    with open(CERT_FILE, "wb") as f:
        f.write(
            cert.public_bytes(serialization.Encoding.PEM)
        )

    logger.info(f"Successfully generated RSA-4096 certificate and private key at {CERTS_DIR}")

    # Set file permissions for safety (unix)
    try:
        os.chmod(KEY_FILE, 0o600)
        os.chmod(CERT_FILE, 0o644)
    except Exception as e:
        logger.debug(f"Could not adjust file permissions: {e}")

    return CERT_FILE, KEY_FILE

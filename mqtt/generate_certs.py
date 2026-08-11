import os
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
from cryptography import x509

def generate_cert(name, is_ca=False, ca_cert=None, ca_key=None):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"V2V"),
        x509.NameAttribute(NameOID.COMMON_NAME, name),
    ])

    if not is_ca:
        issuer = ca_cert.subject

    cert_builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    )

    if is_ca:
        cert_builder = cert_builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )

    sign_key = ca_key if ca_key else private_key
    certificate = cert_builder.sign(
        private_key=sign_key, algorithm=hashes.SHA256()
    )

    return private_key, certificate

def save_cert(private_key, certificate, filename_prefix):
    with open(f"{filename_prefix}.key", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(f"{filename_prefix}.crt", "wb") as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    os.makedirs("certs", exist_ok=True)
    os.chdir("certs")

    print("Generating CA...")
    ca_key, ca_cert = generate_cert(u"CA", is_ca=True)
    save_cert(ca_key, ca_cert, "ca")

    print("Generating Server Cert...")
    server_key, server_cert = generate_cert(u"localhost", is_ca=False, ca_cert=ca_cert, ca_key=ca_key)
    save_cert(server_key, server_cert, "server")

    print("Generating Client Cert...")
    client_key, client_cert = generate_cert(u"client", is_ca=False, ca_cert=ca_cert, ca_key=ca_key)
    save_cert(client_key, client_cert, "client")

    print("Certs generated in certs/")

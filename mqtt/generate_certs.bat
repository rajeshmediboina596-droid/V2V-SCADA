@echo off
mkdir certs
cd certs

echo Generating CA...
openssl req -new -x509 -days 3650 -extensions v3_ca -keyout ca.key -out ca.crt -nodes -subj "/C=US/ST=State/L=City/O=V2V/CN=CA"

echo Generating Server Key and CSR...
openssl genrsa -out server.key 2048
openssl req -out server.csr -key server.key -new -subj "/C=US/ST=State/L=City/O=V2V/CN=localhost"

echo Signing Server Cert...
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3650

echo Generating Client Key and CSR...
openssl genrsa -out client.key 2048
openssl req -out client.csr -key client.key -new -subj "/C=US/ST=State/L=City/O=V2V/CN=client"
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt -days 3650

cd ..
echo Certs generated in certs\

all: generate

.PHONY: all generate fetch-samples make-samples test clean \
        wireshark-ip wireshark-session wireshark-tls-weak wireshark-tls-sni

# Generate Lua dissectors from YAML specifications
generate:
	./tools/generate_all.sh

# Run automated tshark tests against all generated dissectors
test: generate
	./tools/test_dissectors.sh

# Download real public pcap files (not committed; placed as real_sample.*)
fetch-samples:
	./tools/fetch_samples.sh

# Regenerate the committed synthetic sample.pcap files from scratch
make-samples:
	python tools/make_samples.py

clean:
	rm -rf results/

wireshark-ip: generate
	./tools/run_wireshark.sh ip_scoped

wireshark-session: generate
	./tools/run_wireshark.sh session_id

wireshark-tls-weak: generate
	./tools/run_wireshark.sh tls_weak_cipher

wireshark-tls-sni: generate
	./tools/run_wireshark.sh tls_sni_analysis

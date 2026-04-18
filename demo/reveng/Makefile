all: generate

.PHONY: all generate clean wireshark-ip wireshark-session wireshark-tls-weak wireshark-tls-sni

generate:
	./tools/generate_all.sh

clean:
	rm -rf results/

wireshark-ip:
	./tools/run_wireshark.sh ip_scoped

wireshark-session:
	./tools/run_wireshark.sh session_id

wireshark-tls-weak:
	./tools/run_wireshark.sh tls_weak_cipher

wireshark-tls-sni:
	./tools/run_wireshark.sh tls_sni_analysis

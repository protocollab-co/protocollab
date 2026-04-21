.PHONY: all clean wireshark-ip wireshark-session wireshark-tls-weak wireshark-tls-sni

all: results/ip_scoped.lua results/session_id.lua results/tls_weak.lua results/tls_sni.lua

results/%.lua: */%.yaml
	mkdir -p results
	protocollab generate wireshark $< -o $@

wireshark-ip: all
	./tools/run_wireshark.sh ip_scoped

wireshark-session: all
	./tools/run_wireshark.sh session_id

wireshark-tls-weak: all
	./tools/run_wireshark.sh tls_weak_cipher

wireshark-tls-sni: all
	./tools/run_wireshark.sh tls_sni_analysis

clean:
	rm -rf results/

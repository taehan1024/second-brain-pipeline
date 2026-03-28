download:
	python3 scripts/arxiv_downloader.py

download-dry:
	python3 scripts/arxiv_downloader.py --dry-run

convert:
	python3 scripts/pdf_to_md.py

tag:
	python3 scripts/tag_metadata.py --suggest --apply

search:
	python3 scripts/vault_search.py --query "$(QUERY)"

gaps:
	python3 scripts/vault_search.py --gaps-init "$(TOPIC)"

test:
	pytest scripts/

.PHONY: download download-dry convert tag search gaps test

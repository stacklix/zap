.PHONY: pack release install clean

pack:
	python3 scripts/build_workflow.py --channel test

release:
	python3 scripts/build_workflow.py --channel release

install: pack
	open dist/zap.alfredworkflow

clean:
	rm -rf dist/zap-workflow dist/zap.alfredworkflow dist/zap.zip dist/zap-*-workflow dist/zap-*.alfredworkflow

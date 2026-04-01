.PHONY: pack release install install-release clean

pack:
	python3 scripts/build_workflow.py --channel test

release:
	python3 scripts/build_workflow.py --channel release

install: pack
	open dist/zap-test.alfredworkflow

install-release: release
	open dist/zap.alfredworkflow

clean:
	rm -rf dist/zap-workflow dist/zap-test-workflow dist/zap.alfredworkflow dist/zap-test.alfredworkflow dist/zap.zip dist/zap-test.zip dist/zap-*-workflow dist/zap-*.alfredworkflow

.PHONY: pack release clean

pack:
	python3 scripts/build_workflow.py --channel test

release:
	python3 scripts/build_workflow.py --channel release

clean:
	rm -rf dist/zap-workflow dist/zap.alfredworkflow dist/zap.zip dist/zap-*-workflow dist/zap-*.alfredworkflow

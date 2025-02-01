# Makefile for maintainer tasks

PACKAGE=$(shell toml get --toml-path pyproject.toml "tool.setuptools.packages[0]")

po/$(PACKAGE).pot.in:
	mkdir -p po
	find $(PACKAGE) -name "*.py" | xargs xgettext --add-comments=TRANSLATORS --from-code=utf-8 --default-domain=$(PACKAGE) --output=po/$(PACKAGE).pot.in
	$(MAKE) po/$(PACKAGE).pot

po/$(PACKAGE).pot: po/$(PACKAGE).pot.in
	sed -e s/VERSION/$$(grep version pyproject.toml | grep -o "[0-9.]\+")/ < $^ > $@

update-po:
	rm -f po/*.po
	wget --recursive --level=1 --no-directories \
			--accept=po --directory-prefix=po --no-verbose \
			https://translationproject.org/latest/$(PACKAGE)/

compile-po:
	for po in po/*.po; do mo=$(PACKAGE)/locale/$$(basename $${po%.po})/LC_MESSAGES/$(PACKAGE).mo; mkdir -p $$(dirname $$mo); msgfmt --output-file=$$mo $$po; done

update-pofiles:
	$(MAKE) po/$(PACKAGE).pot
	$(MAKE) update-po
	$(MAKE) compile-po

build:
	$(MAKE) update-pofiles
	python -m build

dist:
	git diff --exit-code && \
	rm -rf ./dist && \
	mkdir dist && \
	$(MAKE) build

test:
	tox

release:
	$(MAKE) test && \
	$(MAKE) dist && \
	twine upload dist/* && \
	git tag v$$(grep version pyproject.toml | grep -o "[0-9.]\+") && \
	git push --tags

loc:
	cloc --exclude-content="ptext module" $(PACKAGE)/*.py

.PHONY: dist build

# Makefile for maintainer tasks

po/chambercourt.pot: po/chambercourt.pot.in
	sed -e s/VERSION/$$(grep version pyproject.toml | grep -o "[0-9.]\+")/ < $^ > $@

update-pot:
	$(MAKE) po/chambercourt.pot
	find chambercourt -name "*.py" | xargs xgettext --add-comments=TRANSLATORS --from-code=utf-8 --default-domain=chambercourt --output=po/chambercourt.pot.in

update-po:
	for po in po/*.po; do msgmerge --update $$po po/chambercourt.pot; done

compile-po:
	for po in po/*.po; do mo=chambercourt/locale/$$(basename $${po%.po})/LC_MESSAGES/chambercourt.mo; mkdir -p $$(dirname $$mo); msgfmt --output-file=$$mo $$po; done

update-pofiles:
	$(MAKE) update-pot
	$(MAKE) po/chambercourt.pot
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
	make test
	make dist
	twine upload dist/* && \
	git tag v$$(grep version pyproject.toml | grep -o "[0-9.]\+") && \
	git push --tags

loc:
	cloc --exclude-content="ptext module" chambercourt/*.py

.PHONY: dist build

# Makefile for maintainer tasks

po/chambercourt.pot: po/chambercourt.pot.in
	sed -e s/VERSION/$$(grep version pyproject.toml | grep -o "[0-9.]\+")/ < $^ > $@

update-pot:
	$(MAKE) po/chambercourt.pot
	find chambercourt -name "*.py" | xargs xgettext --add-comments=TRANSLATORS --from-code=utf-8 --default-domain=chambercourt --output=po/chambercourt.pot.in

update-po:
	rm -f po/*.po
	wget --recursive --level=1 --no-directories \
			--accept=po --directory-prefix=po --no-verbose \
			https://translationproject.org/latest/chambercourt/

compile-po:
	for po in po/*.po; do mo=chambercourt/locale/$$(basename $${po%.po})/LC_MESSAGES/chambercourt.mo; mkdir -p $$(dirname $$mo); msgfmt --output-file=$$mo $$po; done

update-pofiles:
	$(MAKE) update-pot
	$(MAKE) po/chambercourt.pot
	$(MAKE) update-po
	$(MAKE) compile-po

announce-pot:
	woger translationproject \
		package=$(toml get --toml-path pyproject.toml "tool.setuptools.packages[0]") \
		package_name=$(toml get --toml-path pyproject.toml project.name) \
		version=$(toml get --toml-path pyproject.toml project.version) \
		home=$(toml get --toml-path pyproject.toml project.urls.Homepage) \
		release_url=https://github.com/rrthomas/chambercourt/releases/download/v$version/$package-$version.tar.gz \
		description=$(toml get --toml-path pyproject.toml project.description)

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
	git push --tags && \
	git diff po/chambercourt.pot.in

loc:
	cloc --exclude-content="ptext module" chambercourt/*.py

.PHONY: dist build

PAPER=graphtrust_nsri

.PHONY: all paper figures clean
all: paper figures

paper:
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

figures:
	latexmk -pdf -interaction=nonstopmode -halt-on-error figures_appendix.tex

clean:
	latexmk -C $(PAPER).tex
	latexmk -C figures_appendix.tex

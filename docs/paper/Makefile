PAPER=GraphTrust_NSRI_Research_Brief
OUT=../deliverables

.PHONY: all paper figures clean
all: paper figures

paper:
	mkdir -p $(OUT)
	latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=$(OUT) $(PAPER).tex

figures:
	mkdir -p $(OUT)
	latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=GraphTrust_Publication_Figures -outdir=$(OUT) figures_appendix.tex

clean:
	latexmk -C -outdir=$(OUT) $(PAPER).tex
	latexmk -C -outdir=$(OUT) figures_appendix.tex

---
title: Insomnia Evidence Base
type: concept
client: velorixa
therapeutic_area: insomnia
sensitivity: client-confidential
sources:
  - id: c9f89994
    cited_for: "Lemborexant efficacy and clean morning cognition in COMISA"
  - id: 7f123b6a
    cited_for: "Lemborexant improves subjective sleep quality, tied to morning alertness"
  - id: be770f60
    cited_for: "Age differences in insomnia symptoms; fatigue as discriminator"
  - id: 9bd3c254
    cited_for: "Insomnia diagnosis raises stroke risk"
  - id: c4738894
    cited_for: "Insomnia among risk factors for respiratory infection"
  - id: 3cc9f6f8
    cited_for: "Valeriana as a variable-quality herbal option"
  - id: e89a8bb3
    cited_for: "Integrative therapies comparable to lorazepam on PSQI"
  - id: de5d5e68
    cited_for: "DAO supplementation in a genetic insomnia subgroup"
  - id: da46906f
    cited_for: "Gut microbiota and metabolites causally linked to insomnia"
  - id: 603ddd73
    cited_for: "miRNA dysregulation in short sleep"
  - id: 0972f56b
    cited_for: "Call for methodological rigour in insomnia trials"
  - id: 5ed073f3
    cited_for: "Deprescribing z-hypnotics in primary care without worsening sleep"
  - id: 2eb2d0ee
    cited_for: "Off-topic oncology source flagged for transparency"
  - id: 135f70e1
    cited_for: "Largely off-topic circadian/breast-cancer source"
  - id: fb5c8d77
    cited_for: "Off-topic schizophrenia source, sleep only as comorbidity"
related:
  - projects/launch-prep
  - entities/lemborexant
  - entities/velorixa
  - concepts/claims-guardrails
status: active
last_updated: 2026-06-01
last_ingest_event: log:2026-06-01-1
---

The body of published research that arrived with the launch-prep seed batch, read and sorted by how directly it bears on the Velorixa story. It is a mixed set: a few sources speak straight to the molecule, several sit in the wider insomnia category, and a handful are off-topic and recorded only so the gaps are visible.

## Definition

Sixteen research PDFs were ingested in the seed batch. None of their text could be extracted locally because the bootstrap environment has no PDF tooling, so every summary in this cluster is drawn from the published abstract read via PubMed by PMID, with the full PDF kept in raw. They group into four bands.

**Closest to the brand: the lemborexant evidence.** [A phase 3 post hoc analysis found lemborexant 10 mg significantly improved insomnia severity versus placebo in patients with comorbid insomnia and mild sleep apnea, without significantly affecting next-morning cognition or alertness, while zolpidem impaired several cognitive domains]^[src:c9f89994]. [A separate post hoc analysis of two phase 3 trials found lemborexant improved patient-reported sleep quality versus placebo, and that morning alertness was the parameter most strongly associated with that improvement]^[src:7f123b6a]. Together these are the only sources that directly support efficacy and tolerability positioning, and both are MLR-sensitive.

**The insomnia category and its burden.** [Working-age adults reported worse nocturnal and daytime insomnia symptoms than older adults, with fatigue a better discriminator than daytime sleepiness]^[src:be770f60], which informs segmentation. On downstream cost, [a clinical diagnosis of insomnia was associated with higher risk of any stroke (HR 1.45)]^[src:9bd3c254], and in a large cohort [insomnia was among the factors associated with increased respiratory infection risk]^[src:c4738894]. These support the seriousness of the category without ever becoming Velorixa claims.

**Category alternatives and mechanism.** The self-care and integrative end is well represented: [Valeriana species modulate neurotransmission with favourable but inconsistent safety, varying by formulation]^[src:3cc9f6f8]; [a randomised trial found a Thai herbal remedy and Cannabis sativa oil comparable to lorazepam on PSQI]^[src:e89a8bb3]; and [a DAO supplement improved sleep quality in a genetic subgroup, with a melatonin synergy]^[src:de5d5e68]. On mechanism, [gut microbiota and plasma metabolites were causally linked to insomnia risk]^[src:da46906f] and [specific miRNAs appear dysregulated in short sleep]^[src:603ddd73]. There is also a standing reminder that [insomnia clinical trial research needs methodological rigour]^[src:0972f56b], which is the discipline the claims work depends on. On the stewardship side, [a brief GP-delivered intervention cut inappropriate z-hypnotic use in older adults from 68.9% to 27.78% while keeping sleep quality stable and improving mood]^[src:5ed073f3], which supports a responsible-use narrative rather than a Velorixa efficacy claim.

**Off-topic decoys, logged honestly.** Three sources do not belong to the insomnia story and are recorded only so the seed batch is fully accounted for: [an oncology safety meta-analysis of elotuzumab in multiple myeloma]^[src:2eb2d0ee], [a bidirectional Mendelian randomization study whose subject is breast cancer and circadian behaviour, with insomnia only as a reverse-direction finding]^[src:135f70e1], and [a review whose primary subject is schizophrenia, touching sleep only as a comorbidity]^[src:fb5c8d77].

## Why it matters here

For the launch, the usable evidence narrows quickly. The lemborexant analyses are the substantiated core; everything else is context that frames the category or, in three cases, noise that should not be cited at all. Keeping the bands explicit protects the claims-guardrail work, because it makes clear which sources can carry a claim and which cannot. Because every summary here rests on an abstract rather than the full text, any claim headed for promotional or MLR use should be confirmed against the full PDF in raw before it is relied upon.

## Related

- [[entities/lemborexant]] (the molecule the strongest sources concern)
- [[concepts/claims-guardrails]] (what may and may not be drawn from this evidence)
- [[projects/launch-prep]]

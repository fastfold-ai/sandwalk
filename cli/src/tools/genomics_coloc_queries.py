"""genomics.coloc: Open Targets GraphQL query text (full + lower-complexity fallback). Split from tools/genomics.py."""

OT_URL = "https://api.platform.opentargets.org/api/v4/graphql"
OT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Step 2: Query Open Targets for credible sets with colocalization data.
# We keep a full query and a lower-complexity fallback query because some
# genes can hit Open Targets GraphQL complexity limits.
QUERY_FULL = """
query geneColoc($ensemblId: String!, $size: Int!, $colocSize: Int!) {
    target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        credibleSets(page: {index: 0, size: $size}) {
            count
            rows {
                studyLocusId
                studyId
                studyType
                study {
                    id
                    studyType
                    traitFromSource
                    diseases {
                        id
                        name
                    }
                    nSamples
                }
                variant {
                    id
                    rsIds
                    chromosome
                    position
                }
                pValueMantissa
                pValueExponent
                beta
                colocalisation(page: {index: 0, size: $colocSize}) {
                    count
                    rows {
                        h4
                        h3
                        clpp
                        colocalisationMethod
                        rightStudyType
                        betaRatioSignAverage
                        numberColocalisingVariants
                        otherStudyLocus {
                            studyLocusId
                            studyId
                            studyType
                            qtlGeneId
                            study {
                                id
                                traitFromSource
                                condition
                                biosample {
                                    biosampleId
                                    biosampleName
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

QUERY_LEAN = """
query geneColocLean($ensemblId: String!, $size: Int!, $colocSize: Int!) {
    target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        credibleSets(page: {index: 0, size: $size}) {
            count
            rows {
                studyLocusId
                studyId
                studyType
                study {
                    id
                    studyType
                    traitFromSource
                    diseases {
                        id
                        name
                    }
                }
                colocalisation(page: {index: 0, size: $colocSize}) {
                    count
                    rows {
                        h4
                        h3
                        clpp
                        colocalisationMethod
                        rightStudyType
                        otherStudyLocus {
                            studyLocusId
                            studyId
                            studyType
                            qtlGeneId
                            study {
                                id
                                traitFromSource
                                condition
                                biosample {
                                    biosampleId
                                    biosampleName
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

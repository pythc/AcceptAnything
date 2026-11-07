"""Shared intake limits; bounding the model request must be visible before submission."""
MAX_DOCUMENTS = 4
PER_DOCUMENT_CHARACTERS = 12_000
MAX_TOTAL_CHARACTERS = 24_000
MAX_REQUIREMENTS_CHARACTERS = 12_000


def limits():
    return dict(max_documents=MAX_DOCUMENTS,per_document_characters=PER_DOCUMENT_CHARACTERS,
                max_total_characters=MAX_TOTAL_CHARACTERS,max_requirements_characters=MAX_REQUIREMENTS_CHARACTERS)


def candidate_order(item):
    from pathlib import PurePosixPath
    path=PurePosixPath(item['path']);stem=path.stem.lower()
    authority=stem in {'prd','requirements','contract','spec','specification'}
    rank=(0 if len(path.parts)==1 and stem=='readme' else 1 if len(path.parts)==1 and authority
          else 2 if path.parts[0]=='docs' and len(path.parts)==2 else 3 if authority else 4)
    return (rank,len(path.parts),item['path'].casefold())

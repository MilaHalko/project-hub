from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from project_hub.db.database import Database
from project_hub.documents.entities import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    Document,
    NewDocument,
    ReplacedFile,
)
from project_hub.projects.entities import NewProject
from project_hub.users.entities import NewUser

pytestmark = pytest.mark.anyio


def _new(project_id: UUID, uploaded_by: UUID, key: str = "projects/p/documents/k") -> NewDocument:
    return NewDocument(
        project_id=project_id,
        name="thesis.pdf",
        content_type=PDF_CONTENT_TYPE,
        size=42,
        storage_key=key,
        uploaded_by=uploaded_by,
    )


async def test_add_returns_document_with_uploader_login(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        added = await uow.documents.add(_new(project.id, mila.id))
        await uow.commit()

    assert type(added) is Document
    assert isinstance(added.id, UUID)
    assert added.created_at.tzinfo is not None
    assert added.created_at == added.updated_at
    assert (added.project_id, added.name, added.content_type, added.size) == (
        project.id,
        "thesis.pdf",
        PDF_CONTENT_TYPE,
        42,
    )
    assert added.storage_key == "projects/p/documents/k"
    assert (added.uploaded_by, added.uploader_login) == (mila.id, "mila")
    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) == added
        assert await uow.documents.get(uuid4()) is None


async def test_add_with_unknown_project_raises_and_uow_stays_usable(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))

        with pytest.raises(Exception):  # noqa: B017
            await uow.documents.add(_new(uuid4(), mila.id, "projects/x/documents/a"))

        added = await uow.documents.add(_new(project.id, mila.id))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) == added


async def test_deleting_project_removes_its_documents(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        other = await uow.projects.add(NewProject(mila.id, "Other", ""))
        gone = await uow.documents.add(_new(project.id, mila.id, "projects/a/documents/1"))
        kept = await uow.documents.add(_new(other.id, mila.id, "projects/b/documents/2"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.projects.delete(project.id) is True
        await uow.commit()

    async with database.unit_of_work() as uow:
        assert await uow.documents.get(gone.id) is None
        assert await uow.documents.get(kept.id) == kept


async def test_deleting_uploader_sets_uploaded_by_none(
    database: Database, migrated_database_url: str
) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        await uow.projects.add_member(project.id, anna.id)
        added = await uow.documents.add(_new(project.id, anna.id))
        await uow.commit()

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("DELETE FROM users WHERE id = %s", (anna.id,))

    async with database.unit_of_work() as uow:
        document = await uow.documents.get(added.id)

    assert document is not None
    assert (document.uploaded_by, document.uploader_login) == (None, None)
    assert (document.id, document.name, document.storage_key) == (
        added.id,
        added.name,
        added.storage_key,
    )


async def test_nothing_stored_without_commit(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        await uow.commit()

    async with database.unit_of_work() as uow:
        added = await uow.documents.add(_new(project.id, mila.id))
        assert await uow.documents.get(added.id) == added

    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) is None


async def test_list_for_project_orders_newest_first_and_filters_project(
    database: Database,
) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        other = await uow.projects.add(NewProject(mila.id, "Other", ""))
        first = await uow.documents.add(_new(project.id, mila.id, "projects/a/documents/1"))
        second = await uow.documents.add(_new(project.id, mila.id, "projects/a/documents/2"))
        elsewhere = await uow.documents.add(_new(other.id, mila.id, "projects/b/documents/3"))
        await uow.commit()

    assert first.created_at == second.created_at
    async with database.unit_of_work() as uow:
        listed = await uow.documents.list_for_project(project.id)
        assert listed == sorted([first, second], key=lambda d: d.id, reverse=True)
        assert await uow.documents.list_for_project(other.id) == [elsewhere]
        assert await uow.documents.list_for_project(uuid4()) == []


async def test_list_for_projects_has_entry_for_every_id(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        one = await uow.projects.add(NewProject(mila.id, "One", ""))
        two = await uow.projects.add(NewProject(mila.id, "Two", ""))
        empty = await uow.projects.add(NewProject(mila.id, "Empty", ""))
        a = await uow.documents.add(_new(one.id, mila.id, "projects/a/documents/1"))
        b = await uow.documents.add(_new(one.id, mila.id, "projects/a/documents/2"))
        c = await uow.documents.add(_new(two.id, mila.id, "projects/b/documents/3"))
        await uow.commit()

    unknown = uuid4()
    async with database.unit_of_work() as uow:
        grouped = await uow.documents.list_for_projects([one.id, two.id, empty.id, unknown])
        assert await uow.documents.list_for_projects([]) == {}

    assert grouped == {
        one.id: sorted([a, b], key=lambda d: (d.created_at, d.id), reverse=True),
        two.id: [c],
        empty.id: [],
        unknown: [],
    }


async def test_replace_file_changes_fields_keeps_created_at(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        anna = await uow.users.add(NewUser("anna", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        await uow.projects.add_member(project.id, anna.id)
        added = await uow.documents.add(_new(project.id, mila.id))
        await uow.commit()

    replacement = ReplacedFile(
        name="notes.docx",
        content_type=DOCX_CONTENT_TYPE,
        size=7,
        storage_key="projects/p/documents/new",
        uploaded_by=anna.id,
    )
    async with database.unit_of_work() as uow:
        replaced = await uow.documents.replace_file(added.id, replacement)
        assert replaced is not None
        assert await uow.documents.get(added.id) == replaced
        assert await uow.documents.replace_file(uuid4(), replacement) is None
        await uow.commit()

    assert (replaced.id, replaced.project_id, replaced.created_at) == (
        added.id,
        added.project_id,
        added.created_at,
    )
    assert (replaced.name, replaced.content_type, replaced.size) == (
        "notes.docx",
        DOCX_CONTENT_TYPE,
        7,
    )
    assert replaced.storage_key == "projects/p/documents/new"
    assert (replaced.uploaded_by, replaced.uploader_login) == (anna.id, "anna")
    assert replaced.updated_at > added.updated_at
    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) == replaced


async def test_replace_file_with_unknown_uploader_raises_and_uow_stays_usable(
    database: Database,
) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        added = await uow.documents.add(_new(project.id, mila.id))
        await uow.commit()

    async with database.unit_of_work() as uow:
        broken = ReplacedFile("n.pdf", PDF_CONTENT_TYPE, 1, "projects/p/documents/n", uuid4())
        with pytest.raises((IntegrityError, psycopg.errors.ForeignKeyViolation)):
            await uow.documents.replace_file(added.id, broken)

        fine = ReplacedFile("ok.pdf", PDF_CONTENT_TYPE, 2, "projects/p/documents/ok", mila.id)
        replaced = await uow.documents.replace_file(added.id, fine)
        await uow.commit()

    assert replaced is not None and replaced.name == "ok.pdf"
    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) == replaced


async def test_delete_returns_row_then_get_is_none(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        added = await uow.documents.add(_new(project.id, mila.id))
        other = await uow.documents.add(_new(project.id, mila.id, "projects/p/documents/o"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        deleted = await uow.documents.delete(added.id)
        assert await uow.documents.delete(uuid4()) is None
        await uow.commit()

    assert deleted == added
    async with database.unit_of_work() as uow:
        assert await uow.documents.get(added.id) is None
        assert await uow.documents.get(other.id) == other


async def test_storage_keys_for_project_only_that_project(database: Database) -> None:
    async with database.unit_of_work() as uow:
        mila = await uow.users.add(NewUser("mila", "hash"))
        project = await uow.projects.add(NewProject(mila.id, "Diploma", ""))
        other = await uow.projects.add(NewProject(mila.id, "Other", ""))
        await uow.documents.add(_new(project.id, mila.id, "projects/a/documents/1"))
        await uow.documents.add(_new(project.id, mila.id, "projects/a/documents/2"))
        await uow.documents.add(_new(other.id, mila.id, "projects/b/documents/3"))
        await uow.commit()

    async with database.unit_of_work() as uow:
        keys = await uow.documents.storage_keys_for_project(project.id)
        assert sorted(keys) == ["projects/a/documents/1", "projects/a/documents/2"]
        assert await uow.documents.storage_keys_for_project(other.id) == ["projects/b/documents/3"]
        assert await uow.documents.storage_keys_for_project(uuid4()) == []

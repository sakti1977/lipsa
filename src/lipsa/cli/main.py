"""
Minimal CLI entrypoint for LIPSA (PR #1 bootstrap).

Provides the legal gate commands and a placeholder for future `search`.
All potentially risky operations must go through the legal layer first.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm
from rich.table import Table

from lipsa import __version__
from lipsa.importers import SalesNavigatorCSVImporter
from lipsa.legal.disclaimer import (
    DISCLAIMER_VERSION,
    audit_log_event,
    get_disclaimer_text,
    log_consent_acknowledgment,
    require_acknowledgment,
)
from lipsa.models.job import DataSourceType
from lipsa.models.post import Filters
from lipsa.scrapers import get_backend
from lipsa.storage import (
    delete_search_job,
    get_audit_events_for_job,
    get_runs_for_job,
    get_search_job,
    list_recent_jobs,
    pause_job,
    resume_job,
    update_search_job,
)
from lipsa.storage.db import get_db_info, get_session, run_migrations  # for db + jobs commands
from lipsa.storage.repositories import (
    bulk_upsert_posts,
    create_job_run,
    create_search_job,
    finish_job_run,
)

app = typer.Typer(
    name="lipsa",
    help="LIPSA - LinkedIn Post Search & Collection (with strong legal guardrails).",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


def _print_legal_banner() -> None:
    """Always show a prominent warning on startup."""
    console.print(
        Panel(
            "[bold red]WARNING:[/bold red] Automated access to LinkedIn services almost certainly "
            "violates LinkedIn's User Agreement (Section 8.2). You may face account bans, "
            "legal action, or regulatory fines. This tool makes risks explicit but does "
            "[bold]not[/bold] provide legal protection.\n\n"
            "See [bold]lipsa legal show[/bold] for the full current disclaimer.\n"
            "You must explicitly acknowledge risks before using collection features.",
            title="[bold red]HIGH LEGAL RISK[/bold red]",
            border_style="red",
        )
    )


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=lambda v: _print_version() if v else None,
        is_eager=True,
    ),
) -> None:
    """LIPSA root callback. Always prints the high-risk banner."""
    _print_legal_banner()


def _print_version() -> None:
    console.print(f"lipsa version {__version__}")
    raise typer.Exit()


@app.command("legal")
def legal_command(
    action: str = typer.Argument(
        "show",
        help="Action: 'show' (default) or 'ack' to record acknowledgment.",
    ),
) -> None:
    """
    Legal & compliance commands.

    - `lipsa legal show` : Display the current full disclaimer and risks.
    - `lipsa legal ack`  : Interactively acknowledge the current risks (required before use).
    """
    if action == "show":
        text = get_disclaimer_text()
        console.print(
            Panel(
                text,
                title=f"Current Disclaimer (version {DISCLAIMER_VERSION})",
                border_style="yellow",
                expand=False,
            )
        )
        console.print(
            "\n[bold]To acknowledge these risks (required before any collection):[/bold]\n"
            "  [cyan]lipsa legal ack[/cyan]\n"
        )
        return

    if action == "ack":
        # Force interactive acknowledgment
        console.print(
            "[yellow]You are about to acknowledge the legal and ethical risks of using LIPSA.[/yellow]"
        )
        console.print("Please read the full text with [cyan]lipsa legal show[/cyan] first if you have not.\n")

        if not Confirm.ask("Do you understand that using this tool likely violates LinkedIn's ToS?", default=False):
            console.print("[red]Acknowledgment not recorded. Exiting.[/red]")
            raise typer.Exit(code=1)

        if not Confirm.ask("Do you accept full responsibility for any consequences (account bans, legal action, regulatory fines, etc.)?", default=False):
            console.print("[red]Acknowledgment not recorded. Exiting.[/red]")
            raise typer.Exit(code=1)

        if not Confirm.ask("Do you confirm you have read and understood the current disclaimer?", default=False):
            console.print("[red]Acknowledgment not recorded. Exiting.[/red]")
            raise typer.Exit(code=1)

        # Record it
        ack_record = log_consent_acknowledgment(
            user_response="accepted_v" + DISCLAIMER_VERSION,
            query_context="cli:legal:ack",
        )
        audit_log_event(
            event_type="consent_ack",
            details={
                "disclaimer_version": DISCLAIMER_VERSION,
                "user_ack": ack_record,
                "source": "cli",
            },
        )

        console.print(
            f"[bold green]✓ Acknowledgment recorded for disclaimer version {DISCLAIMER_VERSION}.[/bold green]\n"
            "You may now use other LIPSA commands (subject to per-job consent in later versions).\n"
            "An audit record has been written to your local ~/.lipsa/ directory."
        )
        return

    console.print(f"[red]Unknown action: {action}. Use 'show' or 'ack'.[/red]")
    raise typer.Exit(code=1)


@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Keyword or hashtag (e.g. '#ai' or 'climate tech')"),
    max_results: int = typer.Option(200, "--max-results", "-n", min=1, max=5000),
    provider: str = typer.Option("apify", "--provider", "-p", help="Backend to use"),
    min_reactions: int | None = typer.Option(None, "--min-reactions", help="Only keep posts with at least this many reactions"),
    source: str = typer.Option(
        "public_scrape",
        "--source",
        help="Data source type (public_scrape | sales_navigator_export | linkedin_data_export | manual_import)",
    ),
    purpose: str | None = typer.Option(
        None,
        "--purpose",
        help="Short description of your lawful basis / intended use (recommended)",
    ),
    export: str | None = typer.Option(
        None,
        "--export",
        "-e",
        help="Export results after collection. Example: --export results.csv or --export results.json",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be collected without actually calling the provider (useful for estimation)",
    ),
) -> None:
    """
    Perform a one-off search/collection.

    This command now supports the Hybrid + Strengthened Guardrails direction:
    - Different data sources have different risk profiles.
    - A purpose / lawful basis declaration is strongly encouraged (and will become mandatory).
    """
    console.print(f"[bold]Search query:[/bold] {query}")
    console.print(f"Source: [cyan]{source}[/cyan] | Provider: [cyan]{provider}[/cyan]")

    # === 1. Legal Gate (non-negotiable) ===
    if not require_acknowledgment(interactive=True, context=f"search:{query}"):
        console.print("[red]Legal acknowledgment required before any collection.[/red]")
        raise typer.Exit(code=1)

    # === 2. Resolve data source type ===
    try:
        data_source = DataSourceType(source)
    except ValueError:
        console.print(f"[red]Invalid --source '{source}'. Valid options: {[e.value for e in DataSourceType]}[/red]")
        raise typer.Exit(code=1) from None

    # === 3. Purpose / Lawful Basis capture (Option 3 - Strengthened Guardrails) ===
    if not purpose:
        console.print("\n[yellow]For better legal defensibility, please provide a short description of your purpose.[/yellow]")
        console.print("Example: 'Internal competitive intelligence for my company' or 'Academic research on AI discourse'")
        purpose = typer.prompt("Purpose / Lawful basis for this collection", default="")

        if not purpose or len(purpose.strip()) < 10:
            console.print("[red]A meaningful purpose is required for compliance reasons.[/red]")
            raise typer.Exit(code=1)

    # === 4. Build filters ===
    filters = Filters(max_results=max_results)
    if min_reactions:
        filters.min_reactions = min_reactions

    # === 5. Create Job + Run (now with data_source and purpose) ===
    session = get_session()
    try:
        job = create_search_job(
            session,
            name=f"One-off: {query[:60]}",
            query=query,
            filters_json=filters.model_dump(),
            disclaimer_version=DISCLAIMER_VERSION,
            data_source_type=data_source.value,
            purpose=purpose.strip(),
            provider_preference=provider,
        )

        run = create_job_run(session, job_id=job.id, provider_used=provider)
        session.commit()

        console.print(f"Job created: [dim]{job.id}[/dim] | Run: [dim]{run.id}[/dim]")
        console.print(f"Data source: [cyan]{data_source.value}[/cyan]")
        console.print(f"Purpose recorded: [dim]{purpose[:80]}{'...' if len(purpose) > 80 else ''}[/dim]")

        # === 6. Execute scraper (only for public_scrape for now) ===
        if data_source == DataSourceType.PUBLIC_SCRAPE:
            backend = get_backend(provider)

            if dry_run:
                console.print("[yellow]--dry-run enabled[/yellow] — no provider call will be made.")
                estimated = min(max_results * 2, 2000)
                console.print(f"Estimated records to fetch: ~{estimated}")
                console.print(f"Data source: {data_source.value}")
                console.print(f"Purpose: {purpose}")
                console.print("[green]Dry run complete. No data was collected.[/green]")
                raise typer.Exit(0)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Searching via {backend.name}...", total=None)
                posts = backend.search_posts(query, filters)
                progress.update(task, description=f"Search complete via {backend.name}")

            inserted, skipped = bulk_upsert_posts(session, posts, job_id=job.id, run_id=run.id)

            finish_job_run(
                session,
                run.id,
                status="success",
                posts_collected=len(posts),
                provider_used=provider,
            )
            session.commit()

            console.print(
                f"\n[bold green]✓ Done[/bold green] — {len(posts)} posts collected "
                f"({inserted} new, {skipped} duplicates)"
            )

            # Optional export (P4 feature)
            if export:
                from lipsa.exporters import export_posts

                job_meta = {
                    "job_id": job.id,
                    "query": query,
                    "data_source_type": data_source.value,
                    "purpose": purpose,
                    "provider": provider,
                }
                try:
                    result = export_posts(
                        posts,
                        export,
                        job_metadata=job_meta,
                    )
                    console.print(f"[green]Exported {result.record_count} records → {result.output_path}[/green]")
                except Exception as ex:
                    console.print(f"[yellow]Warning: Export failed: {ex}[/yellow]")
        else:
            console.print(
                f"\n[yellow]Note: Collection for source '{data_source.value}' is not yet fully implemented.[/yellow]\n"
                "Job and purpose have been recorded. Lower-risk import support is coming next."
            )
            # Still mark the run as completed for tracking
            finish_job_run(session, run.id, status="pending", posts_collected=0)
            session.commit()

        # Audit the purpose as well
        audit_log_event(
            event_type="search_executed",
            details={
                "query": query,
                "data_source_type": data_source.value,
                "purpose": purpose,
                "provider": provider,
                "job_id": job.id,
            },
        )

    except Exception as e:
        console.print(f"[bold red]Search failed:[/bold red] {e}")
        audit_log_event(event_type="search_failed", details={"query": query, "error": str(e)})
        raise typer.Exit(code=1) from None
    finally:
        session.close()


# =============================================================================
# DB management commands (PR #2)
# =============================================================================

db_app = typer.Typer(help="Database management commands (migrations, info, etc.)")


@db_app.command("init")
def db_init(
    force: bool = typer.Option(
        False, "--force", help="Re-apply migrations even if tables already exist (dangerous)"
    ),
) -> None:
    """
    Initialize (or upgrade) the LIPSA SQLite database using Alembic.

    This creates all tables defined in the design (posts, search_jobs, job_runs,
    audit_events, authors, media) with the correct indexes and constraints.
    """

    info = get_db_info()
    console.print(f"Database: [cyan]{info['database_path']}[/cyan]")
    console.print(f"Current size: {info['size_bytes'] / 1024:.1f} KB")

    if info["exists"] and not force:
        console.print(
            "[yellow]Database already exists. Use --force if you really want to re-run migrations.[/yellow]"
        )
        # Still try to upgrade to head (idempotent)
        run_migrations()
        console.print("[green]Migrations brought to latest revision.[/green]")
        return

    console.print("Running Alembic migrations to head...")
    run_migrations()
    console.print("[bold green]✓ Database initialized / upgraded successfully.[/bold green]")

    new_info = get_db_info()
    console.print(f"New size: {new_info['size_bytes'] / 1024:.1f} KB")
    console.print(f"Journal mode: {new_info['journal_mode']}")


@db_app.command("info")
def db_info_cmd() -> None:
    """Show information about the current database."""

    info = get_db_info()
    for key, value in info.items():
        console.print(f"{key}: {value}")


app.add_typer(db_app, name="db")


# =============================================================================
# Jobs commands (for viewing purpose, data source, runs, etc.)
# =============================================================================

jobs_app = typer.Typer(help="Manage and inspect collection jobs (purpose, data source, history)")


@jobs_app.command("list")
def jobs_list(limit: int = typer.Option(20, "--limit", "-n", help="Number of recent jobs to show")) -> None:
    """List recent jobs in a clean table, highlighting purpose and data source."""
    session = get_session()
    try:
        jobs = list_recent_jobs(session, limit=limit)

        if not jobs:
            console.print("[yellow]No jobs found in the database.[/yellow]")
            return

        table = Table(title=f"Recent LIPSA Jobs (last {len(jobs)})", show_lines=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Source", style="magenta")
        table.add_column("Purpose / Lawful Basis", style="dim")
        table.add_column("Created", style="green")
        table.add_column("Last Run", style="yellow")

        for job in jobs:
            source = job.data_source_type or "public_scrape"
            purpose = (job.purpose or "(none recorded)")[:55]
            if job.purpose and len(job.purpose) > 55:
                purpose += "..."

            created = job.created_at.strftime("%Y-%m-%d %H:%M") if job.created_at else ""
            last_run = job.last_run_at.strftime("%Y-%m-%d %H:%M") if job.last_run_at else "-"

            table.add_row(
                job.id,
                job.name[:40],
                source,
                purpose,
                created,
                last_run,
            )

        console.print(table)
        console.print("\n[dim]Use 'lipsa jobs show <job-id>' for full details and runs.[/dim]")
    finally:
        session.close()


@jobs_app.command("show")
def jobs_show(job_id: str) -> None:
    """Show full details for one job, including purpose, data source, and execution history."""
    session = get_session()
    try:
        job = get_search_job(session, job_id)
        if not job:
            console.print(f"[red]Job '{job_id}' not found.[/red]")
            return

        runs = get_runs_for_job(session, job.id)

        # Real post count from the posts table (more reliable than run.posts_collected)
        from sqlalchemy import func, select

        from lipsa.storage.models import PostModel
        real_post_count = session.execute(
            select(func.count(PostModel.id)).where(PostModel.job_id == job.id)
        ).scalar()

        # Job details panel
        details = f"""[bold]ID:[/bold] {job.id}
[bold]Name:[/bold] {job.name}
[bold]Query:[/bold] {job.query}
[bold]Data Source:[/bold] [magenta]{job.data_source_type or 'public_scrape'}[/magenta]
[bold]Purpose / Lawful Basis:[/bold] {job.purpose or '[dim](none recorded)[/dim]'}
[bold]Provider:[/bold] {job.provider_preference or 'default'}
[bold]Created:[/bold] {job.created_at}
[bold]Last Run:[/bold] {job.last_run_at or 'never'}
[bold]Posts in Database:[/bold] {real_post_count}"""

        console.print(Panel(details, title="[bold cyan]Job Details[/bold cyan]", border_style="blue"))

        # Runs table
        if runs:
            run_table = Table(title=f"Runs ({len(runs)})", show_header=True)
            run_table.add_column("Run ID", style="cyan")
            run_table.add_column("Status", style="bold")
            run_table.add_column("Posts", justify="right")
            run_table.add_column("Started")
            run_table.add_column("Finished")
            run_table.add_column("Error", style="red")

            status_style = {
                "success": "green",
                "failed": "red",
                "running": "yellow",
                "pending": "blue",
            }

            for run in runs:
                color = status_style.get(run.status, "white")
                error = (run.error_message or "")[:40]

                run_table.add_row(
                    run.id,
                    f"[{color}]{run.status}[/{color}]",
                    str(run.posts_collected),
                    str(run.started_at)[:19],
                    str(run.finished_at)[:19] if run.finished_at else "-",
                    error,
                )
            console.print(run_table)
        else:
            console.print("[dim]No runs recorded for this job.[/dim]")

        console.print("\n[dim]Tip: 'lipsa jobs export' creates a compliance package for this job.[/dim]")
        if real_post_count > 0:
            console.print("[dim]Tip: Use 'lipsa jobs posts <job-id>' to view actual stored records.[/dim]")

    finally:
        session.close()


@jobs_app.command("posts")
def jobs_posts(
    job_id: str,
    limit: int = typer.Option(10, "--limit", "-n", help="Number of posts to show"),
    format: str = typer.Option("table", "--format", help="Output format: table or json"),
) -> None:
    """Show actual posts stored for a job (useful for debugging blank exports)."""
    from sqlalchemy import select

    from lipsa.storage.models import PostModel

    session = get_session()
    try:
        job = get_search_job(session, job_id)
        if not job:
            console.print(f"[red]Job '{job_id}' not found.[/red]")
            return

        stmt = select(PostModel).where(PostModel.job_id == job.id).limit(limit)
        posts = list(session.execute(stmt).scalars())

        if not posts:
            console.print(f"[yellow]No posts found in the database for job {job_id}.[/yellow]")
            console.print("This is why your exports are blank.")
            console.print("\nPossible reasons:")
            console.print("  - The collection/import did not succeed")
            console.print("  - Posts were not linked to this job_id")
            console.print("  - The run was interrupted before data was saved")
            return

        console.print(f"\n[bold]Posts for job {job_id}[/bold] (showing {len(posts)})\n")

        if format == "json":
            import json
            data = [
                {
                    "post_urn": p.post_urn,
                    "url": p.url,
                    "text": (p.text or "")[:200] + "..." if p.text and len(p.text) > 200 else p.text,
                    "author_name": p.author_name,
                    "reactions_count": p.reactions_count,
                }
                for p in posts
            ]
            console.print(json.dumps(data, indent=2, default=str))
        else:
            table = Table(title=f"Posts from Job {job_id}")
            table.add_column("URN", style="cyan", no_wrap=True)
            table.add_column("Author", style="bold")
            table.add_column("Text", style="dim")
            table.add_column("Reactions", justify="right")

            for p in posts:
                text_preview = (p.text or "")[:80].replace("\n", " ")
                table.add_row(
                    p.post_urn[:22] + "...",
                    p.author_name[:28],
                    text_preview,
                    str(p.reactions_count),
                )
            console.print(table)

    finally:
        session.close()


@jobs_app.command("create")
def jobs_create(
    name: str = typer.Argument(..., help="Human-readable name for the job"),
    query: str = typer.Option(..., "--query", "-q", help="Search query or import description"),
    source: str = typer.Option("public_scrape", "--source", help="Data source type"),
    schedule: str | None = typer.Option(None, "--schedule", help="Cron expression for recurring execution (e.g. '0 9 * * MON')"),
    purpose: str = typer.Option(..., "--purpose", "-p", help="Purpose / lawful basis (required)"),
) -> None:
    """Create a new (optionally recurring) job.

    For scheduled jobs, this will force a fresh consent acknowledgment
    and capture a versioned snapshot (core P5 legal requirement).
    """
    try:
        data_source = DataSourceType(source)
    except ValueError:
        console.print(f"[red]Invalid source. Valid: {[e.value for e in DataSourceType]}[/red]")
        raise typer.Exit(1) from None

    # For recurring jobs, enforce consent snapshot at creation time
    effective_purpose = purpose.strip()
    consent_disclaimer_version = None
    consent_purpose = None
    consent_timestamp = None

    if schedule:
        # Force explicit consent acknowledgment for scheduled jobs
        if not require_acknowledgment(interactive=True, context=f"jobs:create:scheduled:{name}"):
            console.print("[red]Consent acknowledgment is required to create a recurring job.[/red]")
            raise typer.Exit(1)

        consent_disclaimer_version = DISCLAIMER_VERSION
        consent_purpose = effective_purpose
        consent_timestamp = datetime.utcnow()

    session = get_session()
    try:
        job = create_search_job(
            session,
            name=name,
            query=query,
            filters_json={},
            disclaimer_version=DISCLAIMER_VERSION,
            data_source_type=data_source.value,
            purpose=effective_purpose,
            schedule_cron=schedule,
            consent_disclaimer_version=consent_disclaimer_version,
            consent_purpose=consent_purpose,
            consent_timestamp=consent_timestamp,
        )
        session.commit()

        console.print(f"[bold green]✓ Job created:[/bold green] {job.id}")
        console.print(f"  Name: {name}")
        console.print(f"  Source: {data_source.value}")
        if schedule:
            console.print(f"  Schedule: {schedule}")
            console.print(f"  Consent snapshot captured at version {DISCLAIMER_VERSION}")
            console.print("[yellow]Note: Start the scheduler with 'lipsa scheduler start' to run recurring jobs.[/yellow]")

    finally:
        session.close()


@jobs_app.command("update")
def jobs_update(
    job_id: str = typer.Argument(..., help="ID of the job to update"),
    name: str | None = typer.Option(None, "--name", help="New name"),
    query: str | None = typer.Option(None, "--query", "-q", help="New query"),
    schedule: str | None = typer.Option(None, "--schedule", help="New cron schedule (use 'none' to remove)"),
    purpose: str | None = typer.Option(None, "--purpose", "-p", help="New purpose (will require re-ack if changed)"),
) -> None:
    """Update an existing job. Changing schedule or purpose on a recurring job requires re-acknowledgment."""
    session = get_session()
    try:
        job = get_search_job(session, job_id)
        if not job:
            console.print(f"[red]Job {job_id} not found.[/red]")
            return

        is_scheduled = bool(job.schedule_cron) or (schedule and schedule != "none")
        new_schedule = schedule
        if schedule == "none":
            new_schedule = None

        new_purpose = purpose.strip() if purpose else job.purpose

        consent_disclaimer_version = None
        consent_purpose = None
        consent_timestamp = None

        # If this is/was a scheduled job and critical fields are changing, force re-ack
        schedule_changing = (new_schedule is not None) and (new_schedule != job.schedule_cron)
        purpose_changing = new_purpose and (new_purpose != job.purpose)

        if is_scheduled and (schedule_changing or purpose_changing):
            console.print("[yellow]You are modifying a recurring job. Re-acknowledgment of consent is required.[/yellow]")
            if not require_acknowledgment(interactive=True, context=f"jobs:update:{job_id}"):
                console.print("[red]Consent re-acknowledgment required. Update cancelled.[/red]")
                return

            consent_disclaimer_version = DISCLAIMER_VERSION
            consent_purpose = new_purpose
            consent_timestamp = datetime.utcnow()

        updated = update_search_job(
            session,
            job_id,
            name=name,
            query=query,
            schedule_cron=new_schedule,
            purpose=new_purpose,
            consent_disclaimer_version=consent_disclaimer_version,
            consent_purpose=consent_purpose,
            consent_timestamp=consent_timestamp,
        )
        session.commit()

        if updated:
            console.print(f"[green]✓ Job {job_id} updated successfully.[/green]")
            if schedule:
                console.print("[yellow]Note: Restart the scheduler (`lipsa scheduler start`) for schedule changes to apply.[/yellow]")
        else:
            console.print("[red]Update failed.[/red]")
    finally:
        session.close()


@jobs_app.command("delete")
def jobs_delete(
    job_id: str = typer.Argument(..., help="ID of the job to delete"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
) -> None:
    """Delete a job and all its associated runs and data."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete job {job_id}? This cannot be undone.", default=False)
        if not confirm:
            console.print("Aborted.")
            return

    session = get_session()
    try:
        success = delete_search_job(session, job_id)
        session.commit()

        if success:
            console.print(f"[green]✓ Job {job_id} and its runs have been deleted.[/green]")
        else:
            console.print(f"[red]Job {job_id} not found.[/red]")
    finally:
        session.close()


@jobs_app.command("pause")
def jobs_pause(job_id: str = typer.Argument(..., help="ID of the scheduled job to pause")) -> None:
    """Pause a recurring job (removes it from the active schedule)."""
    from lipsa.scheduler import get_scheduler

    session = get_session()
    try:
        success = pause_job(session, job_id)
        session.commit()

        if success:
            # Also remove from running scheduler if active
            scheduler = get_scheduler()
            if scheduler and scheduler.running:
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass  # Job might not be loaded yet

            console.print(f"[yellow]✓ Job {job_id} paused.[/yellow]")
            console.print("It will no longer run until you resume it.")
        else:
            console.print(f"[red]Could not pause job {job_id} (not found or not scheduled).[/red]")
    finally:
        session.close()


@jobs_app.command("resume")
def jobs_resume(
    job_id: str = typer.Argument(..., help="ID of the job to resume"),
    schedule: str = typer.Option(..., "--schedule", help="Cron expression to use when resuming"),
) -> None:
    """Resume a paused job with a (possibly new) schedule."""
    from lipsa.scheduler import get_scheduler, schedule_job

    session = get_session()
    try:
        success = resume_job(session, job_id, new_cron=schedule)
        session.commit()

        if success:
            # Re-add to scheduler if it's running
            scheduler = get_scheduler()
            if scheduler and scheduler.running:
                # Note: Full job execution logic will be wired in later P5 work
                from lipsa.scheduler.aps import _run_scheduled_job
                schedule_job(job_id, schedule, _run_scheduled_job)

            console.print(f"[green]✓ Job {job_id} resumed with schedule: {schedule}[/green]")
            console.print("The job will be picked up the next time the scheduler evaluates it.")
        else:
            console.print(f"[red]Could not resume job {job_id}.[/red]")
    finally:
        session.close()


@jobs_app.command("export")
def jobs_export(
    job_id: str,
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (defaults to ~/.lipsa/exports/job-{id}-compliance.json)",
    ),
    data_format: str | None = typer.Option(
        None,
        "--data-format",
        help="Export actual collected data instead of compliance package. Options: csv, json, excel, parquet",
    ),
) -> None:
    """
    Export a compliance package for a job.

    Includes: job definition, runs, purpose, data source, and all related audit events.
    This is useful for legal review, DPIA, or record-keeping.
    """
    session = get_session()
    try:
        job = get_search_job(session, job_id)
        if not job:
            console.print(f"[red]Job '{job_id}' not found.[/red]")
            raise typer.Exit(1)

        runs = get_runs_for_job(session, job.id)
        audit_events = get_audit_events_for_job(session, job.id)

        # Build the compliance package
        package = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "lipsa_version": __version__,
            "job": {
                "id": job.id,
                "name": job.name,
                "query": job.query,
                "data_source_type": job.data_source_type,
                "purpose": job.purpose,
                "filters": job.filters_json,
                "provider_preference": job.provider_preference,
                "created_at": str(job.created_at),
                "last_run_at": str(job.last_run_at) if job.last_run_at else None,
                "disclaimer_version": job.disclaimer_version,
            },
            "runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "started_at": str(r.started_at),
                    "finished_at": str(r.finished_at) if r.finished_at else None,
                    "posts_collected": r.posts_collected,
                    "estimated_cost_usd": r.estimated_cost_usd,
                    "provider_used": r.provider_used,
                    "error_message": r.error_message,
                }
                for r in runs
            ],
            "audit_events": [
                {
                    "id": e.id,
                    "timestamp": str(e.timestamp),
                    "event_type": e.event_type,
                    "disclaimer_version": e.disclaimer_version,
                    "user_ack": e.user_ack,
                    "details": e.details,
                }
                for e in audit_events
            ],
            "notes": "This package is intended for internal compliance / legal record keeping. It does not constitute legal advice.",
        }

        # Determine output path
        exports_dir = Path.home() / ".lipsa" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        if data_format:
            # Data export mode (P4)
            # Fetch posts for this job
            from sqlalchemy import select

            from lipsa.exporters import export_posts
            from lipsa.storage.models import PostModel

            stmt = select(PostModel).where(PostModel.job_id == job.id)
            post_models = list(session.execute(stmt).scalars())

            if not post_models:
                console.print(f"[yellow]No posts found in the database for job {job_id}.[/yellow]")
                console.print("Nothing to export in data format. The file was not created.")
                console.print("Use 'lipsa jobs posts' to investigate why no data was stored.")
                return

            # Convert to simple dicts
            posts = []
            for pm in post_models:
                p = {
                    "post_urn": pm.post_urn,
                    "url": pm.url,
                    "text": pm.text,
                    "author_name": pm.author_name,
                    "author_headline": pm.author_headline,
                    "author_profile_url": pm.author_profile_url,
                    "author_company": pm.author_company,
                    "posted_at": pm.posted_at,
                    "reactions_count": pm.reactions_count,
                    "comments_count": pm.comments_count,
                    "reposts_count": pm.reposts_count,
                    "content_type": pm.content_type,
                    "is_repost": pm.is_repost,
                    "hashtags": pm.hashtags or [],
                    "mentions": pm.mentions or [],
                }
                posts.append(p)

            job_meta = {
                "job_id": job.id,
                "data_source_type": job.data_source_type,
                "purpose": job.purpose,
            }

            result = export_posts(posts, output or f"job-{job.id}-data", format=data_format, job_metadata=job_meta)
            console.print(f"[bold green][OK] Data exported ({result.record_count} records) → {result.output_path}[/bold green]")
            return

        # Default: compliance package
        if output:
            output_path = Path(output)
        else:
            output_path = exports_dir / f"job-{job.id}-compliance.json"

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(package, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"[bold green][OK] Compliance package exported to:[/bold green] {output_path}")
        console.print(f"Contains {len(runs)} runs and {len(audit_events)} audit events.")

    finally:
        session.close()


app.add_typer(jobs_app, name="jobs")


# =============================================================================
# Import commands for lower-risk sources (Hybrid model)
# =============================================================================

import_app = typer.Typer(
    help="Import data from lower-risk sources (Sales Navigator exports, LinkedIn data downloads, CSVs, etc.)"
)


@import_app.command("sales-nav")
def import_sales_nav(
    file: str = typer.Argument(..., help="Path to Sales Navigator CSV export"),
    purpose: str = typer.Option(..., "--purpose", "-p", help="Purpose / lawful basis for this import (required)"),
    name: str | None = typer.Option(None, "--name", help="Custom name for this import job"),
    export: str | None = typer.Option(
        None,
        "--export",
        "-e",
        help="Export results after import. Example: --export results.csv",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Parse the file and show what would be imported without writing to DB",
    ),
) -> None:
    """
    Import a Sales Navigator people export (CSV).

    This is a significantly lower-risk path than public scraping.
    The data must come from an account you have legitimate access to.
    """
    _run_file_import(
        file_path=file,
        source_type="sales_navigator_export",
        purpose=purpose,
        name=name or f"Sales Nav Import: {Path(file).name}",
        importer_class=SalesNavigatorCSVImporter,
        export=export,
        dry_run=dry_run,
    )


def _run_file_import(
    file_path: str,
    source_type: str,
    purpose: str,
    name: str,
    importer_class: type,
    export: str | None = None,
    dry_run: bool = False,
) -> None:
    """Shared logic for file-based imports."""
    from lipsa.storage.db import get_session
    from lipsa.storage.repositories import bulk_upsert_posts, create_job_run, create_search_job

    # Legal gate
    if not require_acknowledgment(interactive=True, context=f"import:{source_type}"):
        console.print("[red]Legal acknowledgment required before importing data.[/red]")
        raise typer.Exit(1)

    session = get_session()
    try:
        importer = importer_class(purpose=purpose)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Importing from {file_path}...", total=None)
            result = importer.import_from_path(file_path)
            progress.update(task, description="Import parsing complete")

        if dry_run:
            console.print("[yellow]--dry-run enabled[/yellow] — nothing will be written to the database.")
            console.print(f"Would import: {len(result.items)} records")
            console.print(f"Source: {source_type}")
            console.print(f"Purpose: {purpose}")
            console.print("[green]Dry run complete.[/green]")
            return

        if not result.items:
            console.print("[yellow]No valid records found in the file.[/yellow]")
            return

        # Create job with proper source + purpose (strengthened guardrail)
        job = create_search_job(
            session,
            name=name,
            query=f"import:{Path(file_path).name}",
            filters_json={},
            disclaimer_version=DISCLAIMER_VERSION,
            data_source_type=source_type,
            purpose=purpose.strip(),
        )

        run = create_job_run(session, job_id=job.id, provider_used="import")

        inserted, skipped = bulk_upsert_posts(
            session, result.items, job_id=job.id, run_id=run.id
        )

        finish_job_run(
            session,
            run.id,
            status="success",
            posts_collected=inserted,
        )
        session.commit()

        console.print(
            f"[bold green]✓ Import complete[/bold green]\n"
            f"  Job: {job.id}\n"
            f"  Source: {source_type}\n"
            f"  Imported: {inserted} new records\n"
            f"  Skipped (duplicates/invalid): {skipped}\n"
            f"  Purpose recorded: {purpose[:80]}{'...' if len(purpose) > 80 else ''}"
        )

        # Optional export after import (P4)
        if export:
            from lipsa.exporters import export_posts
            job_meta = {
                "job_id": job.id,
                "source_type": source_type,
                "purpose": purpose,
            }
            try:
                result = export_posts(result.items, export, job_metadata=job_meta)
                console.print(f"[green]Exported {result.record_count} records → {result.output_path}[/green]")
            except Exception as ex:
                console.print(f"[yellow]Warning: Export failed: {ex}[/yellow]")

        audit_log_event(
            event_type="import_completed",
            details={
                "source_type": source_type,
                "file": file_path,
                "purpose": purpose,
                "imported": inserted,
                "job_id": job.id,
            },
        )

    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1) from None
    finally:
        session.close()


app.add_typer(import_app, name="import")


# =============================================================================
# Scheduler commands (P5 - Basic Scheduling)
# =============================================================================

scheduler_app = typer.Typer(help="Control the background scheduler for recurring jobs")


@scheduler_app.command("start")
def scheduler_start(foreground: bool = typer.Option(True, "--foreground", help="Run scheduler in foreground (default)")) -> None:
    """Start the APScheduler background scheduler and load all eligible recurring jobs."""
    from lipsa.scheduler import start_scheduler

    console.print("[bold]Starting LIPSA scheduler...[/bold]")
    console.print("Loading scheduled jobs with valid consent snapshots...")

    try:
        start_scheduler()
        console.print("[green]Scheduler started successfully.[/green]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]")

        if foreground:
            # Keep the process alive
            import time
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        from lipsa.scheduler import shutdown_scheduler
        shutdown_scheduler()
        console.print("\n[yellow]Scheduler stopped.[/yellow]")


app.add_typer(scheduler_app, name="scheduler")


# =============================================================================
# Config commands (PR #3)
# =============================================================================

config_app = typer.Typer(help="Configuration and secrets (tokens, etc.)")


@config_app.command("set-token")
def set_token(
    provider: str = typer.Argument(..., help="Provider name (e.g. apify)"),
    token: str = typer.Argument(..., help="API token / key"),
) -> None:
    """Store a provider API token securely using the system keyring."""
    from lipsa.config import set_provider_token

    set_provider_token(provider.lower(), token)
    console.print(f"[green][OK] Token for '{provider}' stored securely in your OS keyring.[/green]")


@config_app.command("get-token")
def get_token(provider: str = typer.Argument(..., help="Provider name")) -> None:
    """Check if a token is stored (does not print the secret)."""
    from lipsa.config import get_provider_token

    token = get_provider_token(provider.lower())
    if token:
        console.print(f"[green]Token for '{provider}' is configured.[/green]")
    else:
        console.print(f"[yellow]No token found for '{provider}'.[/yellow]")


app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()

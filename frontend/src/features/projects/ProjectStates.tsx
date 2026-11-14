// Project states from the SCR-07 and STATES boards.
import Link from 'next/link';

/** 403 and 404 look the same (INV-ACCESS): nothing about the project is shown, not even its id or the server's message. */
export function ProjectNoAccess() {
  return (
    <section className="psl-panel projects__noaccess" aria-labelledby="project-noaccess-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral projects__noaccesstag">NO ACCESS</span>
        <h1 id="project-noaccess-title" className="shell-title">
          You can&rsquo;t open this project
        </h1>
        <p className="projects__plain">
          It belongs to work you don&rsquo;t have access to. Nothing about it is shown here, not even its name.
        </p>
        <p className="projects__plain">
          <Link className="psl-btn psl-btn--dark psl-btn--lg" href="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    </section>
  );
}

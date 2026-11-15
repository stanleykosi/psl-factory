// Project states from the SCR-07 and STATES boards.
import Link from 'next/link';

import { buttonClass, PageTitle, Tag } from '@/components';

/** 403 and 404 look the same (INV-ACCESS): nothing about the project is shown, not even its id or the server's message. */
export function ProjectNoAccess() {
  return (
    <section className="psl-panel projects__noaccess" aria-label="No access">
      <div className="psl-panel__body">
        <Tag tone="neutral" className="projects__noaccesstag">
          NO ACCESS
        </Tag>
        <PageTitle>You can&rsquo;t open this project</PageTitle>
        <p className="projects__plain">
          It belongs to work you don&rsquo;t have access to. Nothing about it is shown here, not even its name.
        </p>
        <p className="projects__plain">
          <Link className={buttonClass('dark', 'lg')} href="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    </section>
  );
}

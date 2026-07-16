import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <div className="flex items-center gap-2">
          <img
            src="/sandwalk-logo-light.svg"
            alt="sandwalk"
            className="h-6 w-auto dark:hidden"
          />
          <img
            src="/sandwalk-logo-dark.svg"
            alt="sandwalk"
            className="hidden h-6 w-auto dark:block"
          />
        </div>
      ),
    },
    githubUrl: 'https://github.com/fastfold-ai/sandwalk',
  };
}

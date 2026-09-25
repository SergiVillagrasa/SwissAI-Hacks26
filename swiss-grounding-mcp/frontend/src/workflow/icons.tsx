import type { ReactNode, SVGProps } from "react";

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export function ArrowLeftIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><path d="M12.5 4.5 6 10l6.5 5.5M6 10h9" /></Icon>;
}

export function HomeIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><path d="M4 9.5 10 4l6 5.5" /><path d="M5.5 8.5V16h9V8.5" /></Icon>;
}

export function WorkflowIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="5" cy="5.5" r="1.6" />
      <circle cx="5" cy="14.5" r="1.6" />
      <circle cx="15" cy="10" r="1.6" />
      <path d="M6.4 6.4 13.6 9.4M6.4 13.6 13.6 10.6" />
    </Icon>
  );
}

export function AgentIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="4.5" y="6" width="11" height="9" rx="2.4" />
      <path d="M10 3.2v2.8M7.6 9.8h.01M12.4 9.8h.01M7.6 15v1.6M12.4 15v1.6" />
    </Icon>
  );
}

export function CheckCircleIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><circle cx="10" cy="10" r="7.2" /><path d="M7 10.2l2 2 4-4.4" /></Icon>;
}

export function XCircleIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><circle cx="10" cy="10" r="7.2" /><path d="M7.6 7.6l4.8 4.8M12.4 7.6l-4.8 4.8" /></Icon>;
}

export function MinusCircleIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><circle cx="10" cy="10" r="7.2" /><path d="M7.2 10h5.6" /></Icon>;
}

export function DotCircleIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><circle cx="10" cy="10" r="7.2" /><circle cx="10" cy="10" r="1.6" fill="currentColor" stroke="none" /></Icon>;
}

export function ChevronDownIcon(props: SVGProps<SVGSVGElement>) {
  return <Icon {...props}><path d="M5.5 8l4.5 4.5L14.5 8" /></Icon>;
}

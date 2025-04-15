import React from "react";

export function ChatFooterSpacer() {
  // A simple component that creates space at the bottom on mobile screens only
  // to prevent content from being hidden behind the fixed footer
  return <div className="h-10 md:h-0 w-full shrink-0" aria-hidden="true" />;
}

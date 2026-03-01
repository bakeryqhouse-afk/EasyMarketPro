import { useMemo } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { createClientSecretFetcher, workflowId } from "../lib/chatkitSession";

export function ChatKitPanel() {
  const getClientSecret = useMemo(
    () => createClientSecretFetcher(workflowId),
    []
  );

  const chatkit = useChatKit({
    api: { getClientSecret },
    composer: {
      placeholder: "How can I help you today?",
    },
    startScreen: {
      greeting: "EasyMarketPro Customer Assistant",
    },
    theme: {
      colors: {
        primary: "#000000",
        secondary: "#B8985F",
        text: "#FFFFFF",
      },
    },
  });

  return (
    <div className="flex h-[90vh] w-full rounded-2xl bg-black shadow-sm transition-colors">
      <ChatKit control={chatkit.control} className="h-full w-full" />
    </div>
  );
}

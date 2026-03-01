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
    colorScheme: "dark",
  });

  return (
    <div className="flex h-[90vh] w-full rounded-2xl shadow-sm transition-colors">
      <ChatKit control={chatkit.control} className="h-full w-full" />
    </div>
  );
}

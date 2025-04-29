import { useState, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

function TypingMessage({ fullText }) {
  const [visibleLines, setVisibleLines] = useState([]);

  useEffect(() => {
    const lines = fullText.split("\n");
    let currentLine = 0;

    const interval = setInterval(() => {
      setVisibleLines((prev) => [...prev, lines[currentLine]]);
      currentLine++;

      if (currentLine >= lines.length) {
        clearInterval(interval);
      }
    }, 500); // Show a new line every 500ms

    return () => clearInterval(interval);
  }, [fullText]);

  return (
    <div className="prose prose-sm">
      {visibleLines.map((line, index) => (
        <div key={index}>
          <ReactMarkdown>{line}</ReactMarkdown>
        </div>
      ))}
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const res = await axios.post("http://localhost:8000/chat", {
        message: input,
      });
      const botMessage = { role: "assistant", content: res.data.response };
      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error(error);
    }

    setInput("");
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col  h-screen  w-screen bg-gray-100">
      {/* Fixed Header */}
      <header className="bg-white shadow-md text-center z-10 py-6">
        <h1 className="text-2xl font-bold">ChatQuery 🤔💡💭</h1>
        <p className="text-sm font-normal text-gray-500 mt-2">
          ✨powered by Messari API
        </p>
      </header>

      {/* Footer Input (moved here) */}
      <div className="bg-white h-[90px] p-4 border-t flex items-center space-x-[10px] z-10 w-[90%] mx-auto">
        <input
          className="flex-1 border rounded-lg text-[30px] p-[10px] focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Conversation Input"
        />
        <button
          className="text-[30px] p-[10px] font-bold rounded-lg"
          onClick={sendMessage}
        >
          Send 💬
        </button>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-6 w-[80%] mx-auto">
        <div className="flex flex-col space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col text-center text-gray-400"></div>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${
                  m.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`flex-col p-[10px] rounded-[30px] shadow-md ${
                    m.role === "user"
                      ? "bg-[#dbeafe] text-[#2563eb] text-[30px]"
                      : "bg-[#d1fae5] text-[#065f46] text-left mt-[30px]"
                  }`}
                >
                  {/* {m.role === "assistant" ? (
                    <div className="prose prose-sm">
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <span>{m.content}</span>
                  )} */}

                  {/* {m.role === "assistant" ? (
                    <div className="prose prose-sm">
                      {m.content.split("\n").map((line, index) => (
                        <div key={index}>
                          <ReactMarkdown>{line}</ReactMarkdown>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span>{m.content}</span>
                  )} */}

                  {m.role === "assistant" ? (
                    <TypingMessage fullText={m.content} />
                  ) : (
                    <span>{m.content}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}

export default App;

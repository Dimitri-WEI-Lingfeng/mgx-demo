import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Resizable, type ResizeCallbackData } from 'react-resizable';
import { Layout, Button, Typography, Space, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getSession } from '@/api/client';
import { ChatPanel } from '@/components/ChatPanel';
import { ResourceTabs } from '@/components/ResourceTabs';
import { useAppStore } from '@/stores/appStore';

const { Content } = Layout;
const { Text } = Typography;

const MIN_LEFT_WIDTH = 280;

export function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { setSelectedFilePath } = useAppStore();

  const { data: session, isLoading, error } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const [leftWidth, setLeftWidth] = useState(window.innerWidth * 0.5);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const initializedRef = useRef(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setContainerSize({ width, height });
      if (!initializedRef.current) {
        setLeftWidth(width * 0.5);
        initializedRef.current = true;
      } else if (width < leftWidth) {
        setLeftWidth(Math.max(MIN_LEFT_WIDTH, width - 100));
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [leftWidth]);

  useEffect(() => {
    return () => setSelectedFilePath(null);
  }, [sessionId, setSelectedFilePath]);

  if (!sessionId) {
    navigate('/');
    return null;
  }

  if (isLoading || !session) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Spin size="large" tip={error ? '加载失败' : '加载中...'} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Text type="danger">加载会话失败</Text>
        <Button className="ml-3" onClick={() => navigate('/')}>返回首页</Button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col  bg-white ">
      <div className="flex items-center justify-between px-4 h-12 border-b border-gray-100! bg-white! shrink-0">
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
            返回
          </Button>
          <Text strong className="text-base">{session.name}</Text>
        </Space>
      </div>

      <div ref={containerRef} className="flex-1 flex min-w-0 min-h-0">
        {/* 左侧：AI 聊天（可拖拽调整宽度） */}
        <div style={{ width: leftWidth, flexShrink: 0 }}>
          <Resizable
            width={leftWidth}
            height={containerSize.height || 600}
            axis="x"
            resizeHandles={['e']}
            minConstraints={[MIN_LEFT_WIDTH, 0]}
            maxConstraints={[containerSize.width > 0 ? Math.max(MIN_LEFT_WIDTH, Math.floor(containerSize.width * 0.5)) : 9999, Infinity]}
            onResize={(_e: React.SyntheticEvent, data: ResizeCallbackData) => setLeftWidth(data.size.width)}
          >
            <div className="h-full w-full flex flex-col border-r border-gray-100 bg-gray-50/50">
              <div className="p-3 border-b border-gray-100 flex-1 min-h-0 flex flex-col">
                <Text strong className="text-sm block mb-2">AI 对话</Text>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <ChatPanel key={session.session_id} sessionId={session.session_id} />
                </div>
              </div>
            </div>
          </Resizable>
        </div>

        {/* 右侧：标签页（文件编辑 / 开发服务器 / 数据库） */}
        <div className="flex-1 flex flex-col min-w-0 bg-white px-4 overflow-hidden">
          <ResourceTabs
            sessionId={session.session_id}
            workspaceId={session.workspace_id}
            appName={session.name}
          />
        </div>
      </div>
    </div>
  );
}

export default SessionDetailPage;

import { useEffect, useState } from 'react';
import { Tabs } from 'antd';
import FileEditorTab from './tabs/FileEditorTab';
import DevServerTab from './tabs/DevServerTab';
import DatabaseTab from './tabs/DatabaseTab';
import { eventBus } from '@/utils/eventBus';

interface ResourceTabsProps {
  sessionId: string;
  workspaceId: string;
  appName: string;
}

export function ResourceTabs({ sessionId, workspaceId, appName }: ResourceTabsProps) {
  const [activeKey, setActiveKey] = useState('editor');

  useEffect(() => {
    const handleSwitchToDevTab = () => setActiveKey('dev');
    eventBus.on('switch-to-dev-tab', handleSwitchToDevTab);
    return () => eventBus.off('switch-to-dev-tab', handleSwitchToDevTab);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        className="flex-1 flex flex-col [&_.ant-tabs-content]:h-full [&_.ant-tabs-tabpane]:h-full"
        items={[
          {
            key: 'editor',
            label: '文件编辑',
            children: (
              <div className="h-full overflow-auto">
                <FileEditorTab workspaceId={workspaceId} />
              </div>
            ),
          },
          {
            key: 'dev',
            label: '开发服务器',
            children: (
              <div className="h-full overflow-auto">
                <DevServerTab sessionId={sessionId} appName={appName} />
              </div>
            ),
          },
          {
            key: 'database',
            label: '数据库',
            children: (
              <div className="h-full overflow-auto">
                <DatabaseTab sessionId={sessionId} />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

export default ResourceTabs;

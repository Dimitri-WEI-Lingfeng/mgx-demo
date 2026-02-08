import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Layout, Dropdown, Input, Button, Card, Space, Typography, message, Modal, Select } from 'antd';
import type { MenuProps } from 'antd';
import { FileTextOutlined, AppstoreOutlined, DownOutlined, PlusOutlined, ArrowUpOutlined, BgColorsOutlined, CloseOutlined, SendOutlined } from '@ant-design/icons';
import { listSessions, createSession } from '@/api/client';
import { useAppStore } from '@/stores/appStore';
import type { Session } from '@/types';
import { useState } from 'react';

const { Title, Text } = Typography;


export function SessionsListPage() {
  const navigate = useNavigate();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [framework, setFramework] = useState('nextjs');
  const [prompt, setPrompt] = useState('');

  const queryClient = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  });

  const setInitialPrompt = useAppStore((state) => state.setInitialPrompt);

  const { mutateAsync: handleCreateSession, isPending: isCreating } = useMutation({
    mutationFn: async (params: { name: string, framework: string }) => {
      const { name, framework } = params;
      if (!name.trim()) {
        message.warning('请输入应用名称');
        return;
      }
      try {
        const session = await createSession(name, framework);
        message.success('创建成功');
        queryClient.invalidateQueries({ queryKey: ['sessions'] });
        setCreateModalOpen(false);
        setName('');
        navigate(`/sessions/${session.session_id}`);
      } catch (err: unknown) {
        message.error(err instanceof Error ? err.message : '创建失败');
      }
    },
  });

  const handleSendMessage = async () => {
    await handleCreateSession({name: prompt.slice(0, 20), framework: 'nextjs'}).then(() => {
      setInitialPrompt(prompt);
    });
  };

  const recommendedSessions = [
    {
      name: 'Todo App',
      description: '一个简单的待办应用',
      framework: 'nextjs',
    },
    {
      name: 'Blog App',
      description: '一个简单的博客应用',
      framework: 'nextjs',
    },
    {
      name: 'Personal Website',
      description: '一个简单的个人网站应用',
      framework: 'nextjs',
    },
  ];

  return (
    <div className="flex h-full w-full min">
      <div className="w-[300px] flex flex-col gap-2 px-4 py-4 border-r border-gray-100 bg-black/2">
        <Text className="text-gray-500 text-lg">项目</Text>
        <div className="mt-3 flex flex-wrap gap-3 max-w-md overflow-y-auto">
          {isLoading ? (
            <Card size="small" className="w-48">加载中...</Card>
          ) : sessions.length === 0 ? (
            <Card size="small" className="w-48 cursor-pointer hover:border-[#1677ff] hover:shadow" loading={isCreating} onClick={() => {
              setCreateModalOpen(true);
            }}>
              <div className="text-gray-400 text-sm">暂无项目，点击创建</div>
            </Card>
          ) : (
            sessions.map((s: Session) => (
              <Card
                key={s.session_id}
                size="small"
                className="w-48 cursor-pointer hover:border-[#1677ff] hover:shadow transition-all"
                onClick={() => navigate(`/sessions/${s.session_id}`)}
              >
                <div className="font-medium truncate">{s.name}</div>
              </Card>
            ))
          )}
          {sessions.length > 0 && (
            <Card size="small" className="w-48 cursor-pointer border-dashed hover:border-[#1677ff]" onClick={() => setCreateModalOpen(true)}>
              <div className="text-gray-400 text-sm flex items-center gap-1">
                <PlusOutlined /> 新建项目
              </div>
            </Card>
          )}
        </div>
      </div>
      <div className="flex flex-col justify-center items-center h-full w-full bg-white">
        <div className="relative flex flex-col items-center gap-4 px-6">

          <Title level={1} className="!mb-4 !font-semibold !text-[2.5rem] text-center">
            把想法变成可销售的{' '}
            <span className="text-[#1677ff]">产品</span>
          </Title>
          <Text className="block text-gray-500 text-center mb-10 max-w-xl">
            AI 员工用于验证想法、构建产品并获取客户。几分钟内完成。无需编码。
          </Text>

          <div className="relative w-full lg:min-w-[500px] xl:min-w-[800px] max-w-2xl flex items-center gap-2 rounded-xl bg-white outline outline-1 outline-gray-200  px-4 py-3 shadow-sm">
            <Input.TextArea
              value={prompt}
              rows={5}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder=""
              variant="borderless"
              className="flex-1 py-1 text-base bg-transparent "
              onPressEnter={() =>  handleSendMessage()}
            />
            <Button disabled={!prompt.trim()} className='absolute! bottom-2 right-2' type="primary" icon={<SendOutlined />} onClick={() => handleSendMessage()} />
          </div>

          <div className="flex mt-10 gap-4">
            {recommendedSessions.map((s) => (
              <Card key={s.name} size="small" className="w-48 cursor-pointer hover:border-[#1677ff] hover:shadow transition-all" onClick={() => {
                setName(s.name);
                setFramework(s.framework);
                handleCreateSession({name: s.name, framework: s.framework}).then(() => {
                  setInitialPrompt(`创建一个 ${s.name} 应用`);
                });
              }}>
                <div className="font-medium truncate">{s.name}</div>
                <div className="text-gray-500 text-sm truncate">{s.description}</div>
              </Card>
            ))}
          </div>

          <Modal
            open={createModalOpen}
            onCancel={() => setCreateModalOpen(false)}
            title="新建应用"
            className="w-full max-w-md shadow-xl"
            okText="创建"
            cancelText="取消"
            onOk={() => handleCreateSession(name)}
          >
            
              <Space direction="vertical" className="w-full" size="middle">
                <div>
                  <Text className="text-gray-600">应用名称</Text>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="my-app"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Text className="text-gray-600">框架</Text>
                  <Select
                    value={framework}
                    onChange={(value) => setFramework(value)}
                    className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
                  >
                    <Select.Option value="nextjs">Next.js</Select.Option>
                  </Select>
                </div>
              </Space>
          </Modal>
        </div>
      </div>
    </div>
  );
}

export default SessionsListPage;

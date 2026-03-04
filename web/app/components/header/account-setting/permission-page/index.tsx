'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { RiCheckboxCircleFill, RiLoader2Line } from '@remixicon/react'
import Avatar from '@/app/components/base/avatar'
import Button from '@/app/components/base/button'
import Checkbox from '@/app/components/base/checkbox'
import Input from '@/app/components/base/input'
import { SimpleSelect } from '@/app/components/base/select'
import { useAppContext } from '@/context/app-context'
import type { MemberPermissionDetail, MemberPermissionSummary } from '@/models/permission'
import {
  fetchMemberPermissions,
  fetchPermissionOverview,
  updateMemberPermissions,
  updateResourcePermissionMode,
} from '@/service/permission'
import { cn } from '@/utils/classnames'

const PermissionPage = () => {
  const { t } = useTranslation()
  const { isCurrentWorkspaceOwner, isCurrentWorkspaceManager } = useAppContext()

  const permissionModeOptions = useMemo(() => [
    { value: 'only_me', name: t('permission.onlyMe', { ns: 'common' }) },
    { value: 'all_team_members', name: t('permission.allTeam', { ns: 'common' }) },
    { value: 'partial_members', name: t('permission.partial', { ns: 'common' }) },
  ], [t])

  const [members, setMembers] = useState<MemberPermissionSummary[]>([])
  const [totalDatasets, setTotalDatasets] = useState(0)
  const [totalApps, setTotalApps] = useState(0)
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null)
  const [memberPermissions, setMemberPermissions] = useState<MemberPermissionDetail | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // 权限编辑状态
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([])
  const [selectedAppIds, setSelectedAppIds] = useState<string[]>([])

  // 加载成员列表
  const loadMembers = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetchPermissionOverview()
      setMembers(response.members)
      setTotalDatasets(response.total_datasets)
      setTotalApps(response.total_apps)
    }
    catch (error) {
      console.error('Failed to load members:', error)
    }
    finally {
      setIsLoading(false)
    }
  }, [])

  // 加载成员权限详情
  const loadMemberPermissions = useCallback(async (memberId: string) => {
    setIsLoading(true)
    try {
      const response = await fetchMemberPermissions(memberId)
      setMemberPermissions(response)
      setSelectedDatasetIds(response.accessible_dataset_ids)
      setSelectedAppIds(response.accessible_app_ids)
    }
    catch (error) {
      console.error('Failed to load member permissions:', error)
    }
    finally {
      setIsLoading(false)
    }
  }, [])

  // 切换资源权限模式
  const handlePermissionModeChange = useCallback(async (
    resourceType: 'dataset' | 'app',
    resourceId: string,
    newMode: string,
  ) => {
    try {
      await updateResourcePermissionMode(resourceType, resourceId, newMode)
      // 重新加载当前成员权限以刷新 UI
      if (selectedMemberId)
        await loadMemberPermissions(selectedMemberId)
      await loadMembers()
    }
    catch (error) {
      console.error('Failed to update permission mode:', error)
    }
  }, [selectedMemberId, loadMemberPermissions, loadMembers])

  // 保存权限
  const handleSave = useCallback(async () => {
    if (!selectedMemberId)
      return

    setIsSaving(true)
    try {
      await updateMemberPermissions(selectedMemberId, {
        dataset_ids: selectedDatasetIds,
        app_ids: selectedAppIds,
      })
      // 重新加载成员列表和权限
      await loadMembers()
      await loadMemberPermissions(selectedMemberId)
    }
    catch (error) {
      console.error('Failed to save permissions:', error)
    }
    finally {
      setIsSaving(false)
    }
  }, [selectedMemberId, selectedDatasetIds, selectedAppIds, loadMembers, loadMemberPermissions])

  // 选择成员
  const handleSelectMember = useCallback((memberId: string) => {
    setSelectedMemberId(memberId)
    loadMemberPermissions(memberId)
  }, [loadMemberPermissions])

  // 切换知识库权限
  const toggleDatasetPermission = useCallback((datasetId: string) => {
    setSelectedDatasetIds(prev =>
      prev.includes(datasetId)
        ? prev.filter(id => id !== datasetId)
        : [...prev, datasetId],
    )
  }, [])

  // 切换应用权限
  const toggleAppPermission = useCallback((appId: string) => {
    setSelectedAppIds(prev =>
      prev.includes(appId)
        ? prev.filter(id => id !== appId)
        : [...prev, appId],
    )
  }, [])

  // 初始加载
  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  // 过滤成员
  const filteredMembers = members.filter(member =>
    member.name.toLowerCase().includes(searchKeyword.toLowerCase())
    || member.email.toLowerCase().includes(searchKeyword.toLowerCase()),
  )

  // 只有管理员可以访问
  if (!isCurrentWorkspaceOwner && !isCurrentWorkspaceManager) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-text-tertiary">{t('permission.noPermission', { ns: 'common' })}</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="mb-4">
        <h1 className="system-xl-semibold text-text-primary">
          {t('permission.title', { ns: 'common' })}
        </h1>
        <p className="system-sm-regular mt-1 text-text-tertiary">
          {t('permission.description', { ns: 'common' })}
        </p>
      </div>

      {/* Content */}
      <div className="flex min-h-0 flex-1 gap-4">
        {/* Member List */}
        <div className="flex w-1/3 flex-col rounded-xl border border-divider-subtle bg-components-panel-bg p-4">
          <div className="mb-3">
            <Input
              value={searchKeyword}
              onChange={e => setSearchKeyword(e.target.value)}
              placeholder={t('permission.searchMember', { ns: 'common' })}
            />
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto">
            {filteredMembers.map(member => (
              <div
                key={member.id}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-lg p-3 transition-colors',
                  selectedMemberId === member.id
                    ? 'bg-state-accent-active'
                    : 'hover:bg-state-base-hover',
                )}
                onClick={() => handleSelectMember(member.id)}
              >
                <Avatar name={member.name} avatar={member.avatar} size={36} />
                <div className="min-w-0 flex-1">
                  <div className="system-sm-medium truncate text-text-secondary">
                    {member.name}
                  </div>
                  <div className="system-xs-regular truncate text-text-tertiary">
                    {member.email}
                  </div>
                </div>
                <div className="text-right">
                  <div className="system-xs-medium text-text-tertiary">
                    {member.dataset_count}/{totalDatasets} {t('permission.datasets', { ns: 'common' })}
                  </div>
                  <div className="system-xs-medium text-text-tertiary">
                    {member.app_count}/{totalApps} {t('permission.apps', { ns: 'common' })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Permission Editor */}
        <div className="flex flex-1 flex-col rounded-xl border border-divider-subtle bg-components-panel-bg p-4">
          {selectedMemberId && memberPermissions
            ? (
                <>
                  {/* Selected Member Info */}
                  <div className="mb-4 flex items-center gap-3 border-b border-divider-subtle pb-4">
                    <Avatar name={memberPermissions.member.name} avatar={memberPermissions.member.avatar} size={48} />
                    <div>
                      <div className="system-md-semibold text-text-secondary">
                        {memberPermissions.member.name}
                      </div>
                      <div className="system-sm-regular text-text-tertiary">
                        {memberPermissions.member.email}
                      </div>
                    </div>
                  </div>

                  {/* Permissions */}
                  <div className="flex-1 space-y-6 overflow-y-auto">
                    {/* Dataset Permissions */}
                    <div>
                      <h3 className="system-sm-semibold mb-3 text-text-secondary">
                        {t('permission.datasetAccess', { ns: 'common' })}
                      </h3>
                      <div className="space-y-2">
                        {memberPermissions.datasets.map(dataset => (
                          <div
                            key={dataset.id}
                            className="flex items-center gap-3 rounded-lg border border-divider-subtle p-3"
                          >
                            <Checkbox
                              checked={selectedDatasetIds.includes(dataset.id)}
                              onCheck={() => toggleDatasetPermission(dataset.id)}
                              disabled={dataset.permission !== 'partial_members'}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="system-sm-medium text-text-secondary">
                                {dataset.name}
                              </div>
                            </div>
                            <SimpleSelect
                              className="!w-[140px]"
                              items={permissionModeOptions}
                              defaultValue={dataset.permission}
                              onSelect={item => handlePermissionModeChange('dataset', dataset.id, item.value as string)}
                              notClearable
                            />
                            {dataset.has_access && (
                              <RiCheckboxCircleFill className="h-5 w-5 shrink-0 text-util-colors-green-green-600" />
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* App Permissions */}
                    <div>
                      <h3 className="system-sm-semibold mb-3 text-text-secondary">
                        {t('permission.appAccess', { ns: 'common' })}
                      </h3>
                      <div className="space-y-2">
                        {memberPermissions.apps.map(app => (
                          <div
                            key={app.id}
                            className="flex items-center gap-3 rounded-lg border border-divider-subtle p-3"
                          >
                            <Checkbox
                              checked={selectedAppIds.includes(app.id)}
                              onCheck={() => toggleAppPermission(app.id)}
                              disabled={app.permission !== 'partial_members'}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="system-sm-medium text-text-secondary">
                                {app.name}
                              </div>
                            </div>
                            <SimpleSelect
                              className="!w-[140px]"
                              items={permissionModeOptions}
                              defaultValue={app.permission}
                              onSelect={item => handlePermissionModeChange('app', app.id, item.value as string)}
                              notClearable
                            />
                            {app.has_access && (
                              <RiCheckboxCircleFill className="h-5 w-5 shrink-0 text-util-colors-green-green-600" />
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="mt-4 flex justify-end border-t border-divider-subtle pt-4">
                    <Button
                      variant="primary"
                      onClick={handleSave}
                      disabled={isSaving}
                    >
                      {isSaving && <RiLoader2Line className="mr-1 h-4 w-4 animate-spin" />}
                      {t('operation.save', { ns: 'common' })}
                    </Button>
                  </div>
                </>
              )
            : (
                <div className="flex h-full items-center justify-center">
                  <p className="system-sm-regular text-text-tertiary">
                    {t('permission.selectMember', { ns: 'common' })}
                  </p>
                </div>
              )}
        </div>
      </div>
    </div>
  )
}

export default PermissionPage

'use client'

import { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { BrandLockup, Button, Input, Surface } from '@/src/components/ui'
import { useCurrentUser } from '@/src/hooks/useAuth'
import { useUpdateProfile } from '@/src/hooks/useProfile'

export function ProfileScreen() {
  const router = useRouter()
  const { data: user } = useCurrentUser()
  const updateProfile = useUpdateProfile()
  const [name, setName] = useState(user?.name ?? '')
  const [sportTeam, setSportTeam] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const response = await updateProfile.mutateAsync({
      name: name.trim(),
      sport_team: sportTeam.trim(),
      selected_role: 'athlete',
    })
    router.push(response.next_route)
  }

  return (
    <main className="pb-stage relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
      <HorizonBackground />
      <Surface className="relative z-10 w-full max-w-[460px] p-8">
        <BrandLockup />
        <h1 className="mt-8 font-display text-2xl font-bold text-fg-1">Complete your profile</h1>
        <p className="mt-2 text-sm text-fg-3">Add the basics Playbook needs before opening chat.</p>
        <form className="mt-7 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-semibold text-fg-2">
            Name
            <Input onChange={(event) => setName(event.target.value)} required value={name} />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-fg-2">
            Sport or team
            <Input
              onChange={(event) => setSportTeam(event.target.value)}
              placeholder="Basketball"
              required
              value={sportTeam}
            />
          </label>
          {updateProfile.error && <p className="text-sm text-danger">{updateProfile.error.message}</p>}
          <Button disabled={updateProfile.isPending} size="lg" type="submit">
            Continue to chat
          </Button>
        </form>
      </Surface>
    </main>
  )
}

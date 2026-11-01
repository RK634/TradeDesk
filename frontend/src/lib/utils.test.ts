import { describe, expect, it } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('combines conditional classes and resolves Tailwind conflicts', () => {
    expect(cn('p-2', false && 'hidden', 'p-4', 'text-sm')).toBe('p-4 text-sm')
  })
})

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PageHeader from '../PageHeader.vue'

describe('page heading ownership', () => {
  it('keeps one DOM h1 even when mobile copy differs', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Alle Aufnahmen', mobileTitle: 'Aufnahmen' } })
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.find('h1').text()).toContain('Alle Aufnahmen')
    expect(wrapper.find('h1').text()).toContain('Aufnahmen')
  })
})

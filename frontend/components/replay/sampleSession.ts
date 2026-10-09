/**
 * Sample recorded session data and workflow steps for rrweb replay and SVG overlay testing.
 */

import type { eventWithTime } from '@rrweb/types';
import type { ReplayStep } from './types';

/**
 * Valid sample rrweb event stream simulating an automated session in Gitea repository creation.
 */
export const SAMPLE_RRWEB_EVENTS: eventWithTime[] = [
  // Event 0: Meta event specifying recorded viewport dimensions (1280x720)
  {
    type: 4,
    data: {
      href: 'http://localhost:3000/repo/create',
      width: 1280,
      height: 720,
    },
    timestamp: 1000,
  },
  // Event 1: DomContentLoaded event
  {
    type: 0,
    data: {},
    timestamp: 1050,
  },
  // Event 2: Window Load event
  {
    type: 1,
    data: {},
    timestamp: 1100,
  },
  // Event 3: Full DOM Snapshot
  {
    type: 2,
    data: {
      node: {
        id: 1,
        type: 0, // Document
        childNodes: [
          {
            id: 2,
            type: 1, // DocumentType
            name: 'html',
            publicId: '',
            systemId: '',
          },
          {
            id: 3,
            type: 2, // Element (html)
            tagName: 'html',
            attributes: { lang: 'en' },
            childNodes: [
              {
                id: 4,
                type: 2, // Element (head)
                tagName: 'head',
                attributes: {},
                childNodes: [
                  {
                    id: 5,
                    type: 2,
                    tagName: 'title',
                    attributes: {},
                    childNodes: [{ id: 6, type: 3, textContent: 'Create Repository - Gitea' }],
                  },
                ],
              },
              {
                id: 7,
                type: 2, // Element (body)
                tagName: 'body',
                attributes: { class: 'bg-gray-100 text-gray-900 p-8' },
                childNodes: [
                  {
                    id: 8,
                    type: 2, // Heading
                    tagName: 'h1',
                    attributes: { class: 'text-2xl font-bold mb-4' },
                    childNodes: [{ id: 9, type: 3, textContent: 'New Repository' }],
                  },
                  {
                    id: 10,
                    type: 2, // Form
                    tagName: 'form',
                    attributes: { action: '/repo/create', method: 'post' },
                    childNodes: [
                      {
                        id: 11,
                        type: 2, // Owner selection dropdown
                        tagName: 'select',
                        attributes: { id: 'owner_id', name: 'owner_id', class: 'border p-2 mb-4 block w-64' },
                        childNodes: [
                          {
                            id: 12,
                            type: 2,
                            tagName: 'option',
                            attributes: { value: '1', selected: 'selected' },
                            childNodes: [{ id: 13, type: 3, textContent: 'krama-agent' }],
                          },
                        ],
                      },
                      {
                        id: 14,
                        type: 2, // Repository Name input
                        tagName: 'input',
                        attributes: {
                          id: 'repo_name',
                          name: 'repo_name',
                          type: 'text',
                          placeholder: 'Repository Name',
                          class: 'border p-2 mb-4 block w-64',
                        },
                        childNodes: [],
                      },
                      {
                        id: 15,
                        type: 2, // Submit button
                        tagName: 'button',
                        attributes: {
                          id: 'submit_btn',
                          type: 'submit',
                          class: 'bg-green-600 text-white px-4 py-2 rounded',
                        },
                        childNodes: [{ id: 16, type: 3, textContent: 'Create Repository' }],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      initialOffset: { left: 0, top: 0 },
    },
    timestamp: 1200,
  },
  // Event 4: IncrementalSnapshot - Mouse move toward repository name field
  {
    type: 3,
    data: {
      source: 1, // MouseInteraction / MouseMove
      positions: [
        { x: 100, y: 150, id: 7, timeOffset: 300 },
        { x: 180, y: 220, id: 14, timeOffset: 500 },
      ],
    },
    timestamp: 1700,
  },
  // Event 5: IncrementalSnapshot - Mouse interaction (click) on repository name field
  {
    type: 3,
    data: {
      source: 2, // MouseInteraction
      type: 2, // Click
      id: 14,
      x: 200,
      y: 225,
    },
    timestamp: 2200,
  },
  // Event 6: IncrementalSnapshot - Input change (typing repository name)
  {
    type: 3,
    data: {
      source: 5, // Input
      id: 14,
      text: 'demo-krama-repo',
      isChecked: false,
    },
    timestamp: 2600,
  },
  // Event 7: IncrementalSnapshot - Mouse move toward submit button
  {
    type: 3,
    data: {
      source: 1, // MouseMove
      positions: [
        { x: 200, y: 225, id: 14, timeOffset: 200 },
        { x: 230, y: 290, id: 15, timeOffset: 600 },
      ],
    },
    timestamp: 3200,
  },
  // Event 8: IncrementalSnapshot - Click create repository button
  {
    type: 3,
    data: {
      source: 2, // Click
      type: 2,
      id: 15,
      x: 230,
      y: 290,
    },
    timestamp: 3800,
  },
];

/**
 * Workflow steps annotated with bounding boxes in page CSS pixels (for 1280x720 canvas).
 */
export const SAMPLE_REPLAY_STEPS: ReplayStep[] = [
  {
    id: 'step-owner-select',
    seq: 1,
    instruction: 'Select owner account "krama-agent"',
    timeOffset: 200,
    bbox: [64, 120, 260, 42],
    cursorPosition: { x: 194, y: 141 },
    status: 'completed',
  },
  {
    id: 'step-repo-name-input',
    seq: 2,
    instruction: 'Enter repository name "demo-krama-repo"',
    timeOffset: 1200,
    bbox: { x: 64, y: 190, width: 260, height: 42 },
    cursorPosition: { x: 200, y: 211 },
    status: 'active',
  },
  {
    id: 'step-submit-create-repo',
    seq: 3,
    instruction: 'Click "Create Repository" button',
    timeOffset: 2800,
    bbox: [64, 260, 160, 44],
    cursorPosition: { x: 144, y: 282 },
    status: 'pending',
  },
];

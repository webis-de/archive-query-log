import { UserData } from './models/user-data.model';

export const MOCK_USER_DATA: UserData = {
  user: {
    name: 'Test User',
    institute: 'Test Institute',
    avatarUrl:
      'https://plus.unsplash.com/premium_photo-1689977807477-a579eda91fa2?q=80&w=1170&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
  },
  projects: [
    {
      id: '1',
      name: 'Group Item 1',
      items: [
        { id: '1', name: 'Search Item 1' },
        { id: '2', name: 'Search Item 2' },
        { id: '3', name: 'Search Item 3' },
      ],
    },
    {
      id: '2',
      name: 'Group Item 2',
      items: [
        { id: '4', name: 'Search Item A' },
        { id: '5', name: 'Search Item B' },
      ],
    },
    {
      id: '3',
      name: 'Group Item 3',
      items: [
        { id: '6', name: 'Search Item abc' },
        { id: '7', name: 'Search Item def' },
        { id: '8', name: 'Search Item ghi' },
      ],
    },
    {
      id: '4',
      name: 'Group Item',
      items: [],
    },
    {
      id: '5',
      name: 'Group Item',
      items: [],
    },
    {
      id: '6',
      name: 'Group Item',
      items: [],
    },
    {
      id: '7',
      name: 'Group Item',
      items: [],
    },
    {
      id: '8',
      name: 'Group Item',
      items: [],
    },
    {
      id: '9',
      name: 'Group Item',
      items: [],
    },
    {
      id: '10',
      name: 'Group Item',
      items: [],
    },
    {
      id: '11',
      name: 'Group Item',
      items: [],
    },
    {
      id: '12',
      name: 'Group Item',
      items: [],
    },
    {
      id: '13',
      name: 'Group Item',
      items: [],
    },
    {
      id: '14',
      name: 'Group Item',
      items: [],
    },
  ],
};

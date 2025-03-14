<template>
    <div>
      <h2>Statistics</h2>
      <div class="py-4"></div>
      <v-data-table :items="statistics" item-key="name" items-per-page="10" class="table-shadow mx-auto">
      </v-data-table>
    </div>
  </template>
  
  <script>
  export default {
    props: {
      statistics: {
        type: Array,
        required: true,
      },
    },
  };
  </script>
  
  <style>
  .table-shadow {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
    margin: 0 16px;
  }
  </style>
<template>
  <v-container class="fill-height d-flex flex-column">
    <v-responsive class="flex-grow-1">
      <div class="content">
        <Header />
        <div class="py-10"></div>
        <StatisticsTable :statistics="statistics" />
        <div class="py-10"></div>
        <ProgressTable :progress="progress" />
      </div>
    </v-responsive>
    <Footer />
  </v-container>
</template>

<script>
import Header from './components/Header.vue';
import StatisticsTable from './components/StatisticsTable.vue';
import ProgressTable from './components/ProgressTable.vue';
import Footer from './components/Footer.vue';
import { fetchData } from './client.js';

export default {
  components: {
    Header,
    StatisticsTable,
    ProgressTable,
    Footer,
  },
  data() {
    return {
      statistics: [],
      progress: [],
    };
  },
  async mounted() {
    try {
      this.statistics = await fetchData('/statistics');
      this.progress = await fetchData('/progress');
    } catch (error) {
      console.error(error.message);
    }
  },
};
</script>

<style>
.fill-height {
  height: 100%;
}

.d-flex {
  display: flex;
}

.flex-column {
  flex-direction: column;
}

.flex-grow-1 {
  flex-grow: 1;
}

.align-center {
  align-items: center;
}

.justify-center {
  justify-content: center;
}

.mx-auto {
  margin-left: auto;
  margin-right: auto;
}

.content {
  padding-bottom: 80px;
}
</style>


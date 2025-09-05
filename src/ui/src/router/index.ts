import { createRouter, createWebHistory } from 'vue-router'
import BlankLayout from '@/views/layouts/BlankLayout.vue'
import DefaultLayout from '@/views/layouts/DefaultLayout.vue'
import ExlinkLayout from '@/views/layouts/ExlinkLayout.vue'
import auth from '@/utils/auth'
import { useGenerateAccessTokenWithExlink } from '@/hooks/use-web-app'
import { useCredentialStore } from '@/stores/credential'

const { accessTokenWithExLink, handleExlinkGenerateAccessToken } = useGenerateAccessTokenWithExlink()

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      children: [
        {
          path: '',
          redirect: 'home'
        },
        {
          path: 'home',
          name: 'pages-home',
          component: () => import('@/views/pages/HomeView.vue')
        },
        {
          path: 'space',
          name: 'space',
          component: () => import('@/views/space/SpaceLayoutView.vue'),
          children: [
            {
              path: 'apps',
              name: 'space-apps-list',
              component: () => import('@/views/space/apps/ListView.vue')
            },
            {
              path: 'tools',
              name: 'space-tools-list',
              component: () => import('@/views/space/tools/ListView.vue')
            },
            {
              path: 'workflows',
              name: 'space-workflows-list',
              component: () => import('@/views/space/workflows/ListView.vue')
            },
            {
              path: 'datasets',
              name: 'space-datasets-list',
              component: () => import('@/views/space/datasets/ListView.vue')
            },
            {
              path: 'mcp-tools',
              name: 'mcp-tool-list',
              component: () => import('@/views/space/mcp-tools/ListView.vue')
            }
          ]
        },
        {
          path: 'space/datasets/:dataset_id/documents',
          name: 'space-datasets-documents-list',
          component: () => import('@/views/space/datasets/documents/ListView.vue')
        },
        {
          path: 'space/datasets/:dataset_id/documents/create',
          name: 'space-datasets-documents-create',
          component: () => import('@/views/space/datasets/documents/CreateView.vue')
        },
        {
          path: 'space/datasets/:dataset_id/documents/:document_id/segments',
          name: 'space-datasets-documents-segments-list',
          component: () => import('@/views/space/datasets/documents/segments/ListView.vue')
        },
        {
          path: "store/apps",
          name: "store-apps-list",
          component: () => import('@/views/store/apps/ListView.vue')
        },
        {
          path: "store/tools",
          name: "store-tools=list",
          component: () => import('@/views/store/tools/ListView.vue')
        },
        {
          path: 'openapi',
          component: () => import('@/views/openapi/OpenAPILayoutView.vue'),
          children: [
            {
              path: '',
              name: 'openapi-index',
              component: () => import('@/views/openapi/IndexView.vue')
            },
            {
              path: 'api-keys',
              name: 'openapi-keys',
              component: () => import('@/views/openapi/api-keys/ListView.vue')
            }
          ]
        }
      ]
    },
    {
      path: '/',
      component: BlankLayout,
      children: [
        {
          path: 'auth/login',
          name: 'auth-login',
          component: () => import('@/views/auth/LoginForm.vue')
        },
        {
          path: 'auth/authorize/:provider_name',
          name: 'auth-authorize',
          component: () => import('@/views/auth/AuthorizeView.vue')
        },
        {
          path: 'space/apps',
          component: () => import('@/views/space/apps/AppLayoutList.vue'),
          children: [
            {
              path: ':app_id',
              name: 'space-apps-detail',
              component: () => import('@/views/space/apps/DetailView.vue')
            },
            {
              path: ':app_id/published',
              name: 'space-apps-published',
              component: () => import('@/views/space/apps/PublishedView.vue')
            },
            {
              path: ':app_id/analysis',
              name: 'space-apps-analysis',
              component: () => import('@/views/space/apps/AnalysisView.vue')
            }
          ]
        },
        {
          path: "space/workflows/:workflow_id",
          name: "space-workflows-detail",
          component: () => import('@/views/space/workflows/DetailView.vue')
        },
        {
          path: "web-apps/:token",
          name: "web-apps-index",
          component: () => import('@/views/web-apps/IndexView.vue')
        },
        {
          path: "ex-link-web-app/:ex_link_token/:end_user_id",
          name: "ex-link-web-app-index",
          component: () => import('@/views/web-apps/IndexView.vue')
        },
        {
          path: "/errors/404",
          name: "errors-not-found",
          component: () => import("@/views/errors/NotFoundView.vue")
        },
        {
          path: "/errors/403",
          name: 'errors-forbidden',
          component: () => import("@/views/errors/ForbiddenView.vue")
        }
      ]
    },
    {
      path: '/ex-link',
      component: ExlinkLayout,
      children: [
        {
          path: "ex-link-switch-web-app/:end_user_id",
          name: "ex-link-switch-web-app-index",
          component: () => import('@/views/web-apps/ExlinkView.vue')
        },
        {
          path: "ex-link-web-app/:ex_link_token/:end_user_id",
          name: "ex-link-inner-web-app-index",
          component: () => import('@/views/web-apps/IndexView.vue')
        }
      ]
    }
  ]
})

router.beforeEach(async (to, from) => {
  const credentialStore = useCredentialStore()
  // todo: 2025-04-10 sam exLink实现，如果是exlink路由，要请求外链验证接口生成临时认证，以确保后面的逻辑正常
  if (["ex-link-web-app-index", "ex-link-inner-web-app-index"].includes(to.name as string)) {
    // 通过ex_link_token换来认证信息
    const ex_link_token = to.params['ex_link_token'] as string
    await handleExlinkGenerateAccessToken(ex_link_token)
    credentialStore.update(accessTokenWithExLink.value)
  }

  if (!auth.isLogin() && !['auth-login', 'auth-authorize', 'ex-link-switch-web-app-index'].includes(to.name as string)) {
    return {path: '/auth/login'}
  }
})

export default router

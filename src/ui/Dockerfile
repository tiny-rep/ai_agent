FROM node:20 as builder

WORKDIR /app/web

COPY . .

RUN yarn install

ENV VITE_API_PREFIX=/api

RUN yarn build

# 第二阶段
FROM nginx:alpine as production
COPY --from=builder /app/web/dist /usr/share/nginx/html
COPY --from=builder /app/web/docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 设备文件夹权限 775
RUN find /usr/share/nginx/html -type d -exec chmod 755 {} \;
#设置文件权限 644
RUN find /usr/share/nginx/html -type f -exec chomd 644 {} \;

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
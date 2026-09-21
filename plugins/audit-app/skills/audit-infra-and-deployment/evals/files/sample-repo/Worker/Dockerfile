# syntax=docker/dockerfile:1
# Negative fixture: multi-stage, pinned by tag and digest, non-root, no secrets.
FROM mcr.microsoft.com/dotnet/sdk:8.0@sha256:3c3a9ab4a3e4f1c2b7d6e5f40a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b AS build
WORKDIR /src
COPY Worker.csproj ./
RUN dotnet restore Worker.csproj
COPY . .
RUN dotnet publish Worker.csproj -c Release -o /app/publish --no-restore /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine@sha256:9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a0 AS final
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
USER $APP_UID
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["dotnet", "Worker.dll"]

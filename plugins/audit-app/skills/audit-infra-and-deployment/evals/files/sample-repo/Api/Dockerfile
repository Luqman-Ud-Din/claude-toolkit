# Inventory API image - built and run in one stage
FROM mcr.microsoft.com/dotnet/sdk:latest
WORKDIR /src
COPY . .
COPY secrets.json /app/secrets.json
ENV ConnectionStrings__Default="Server=sql;Database=inventory;User Id=sa;Password=P@ssw0rd123!"
RUN dotnet publish Api.csproj -c Release -o /app
WORKDIR /app
USER root
EXPOSE 80
ENV ASPNETCORE_URLS=http://+:80
ENTRYPOINT ["dotnet", "Api.dll"]

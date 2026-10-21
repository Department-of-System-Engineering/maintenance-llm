IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='LlmKnowledgeBase' and xtype='U')
BEGIN
    CREATE TABLE [LlmKnowledgeBase] (
        [Id] NVARCHAR(255) PRIMARY KEY,
        [Document] NVARCHAR(MAX) NULL,
        [Metadata] NVARCHAR(MAX) NULL,
        [EmbeddingBin] VARBINARY(MAX) NOT NULL
    )
END